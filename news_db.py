import os
import sqlite3
import time
import traceback
from datetime import datetime

import feedparser
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


class NewsDatabase:
    def __init__(self, filename="news.sqlite"):
        self.filename = filename
        self.conn = None
        self.create_table()

    def create_table(self):
        try:
            self.connect()
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS article (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT,
                    is_topics INTEGER,
                    url TEXT UNIQUE,
                    published_date DATETIME,
                    title TEXT,
                    body TEXT
                )
            ''')
        finally:
            self.close()

    def connect(self, filename=None):
        if not filename:
            filename = self.filename
        self.conn = sqlite3.connect(filename)
    
    def close(self):
        if self.conn:
            self.conn.close()
        self.conn = None

    def insert_article(self, category, is_topics, url, published_date, title, body):
        success = False
        try:
            self.connect()
            self.conn.execute('BEGIN EXCLUSIVE')

            cursor = self.conn.execute('SELECT COUNT(*) FROM article WHERE url=?', (url,))
            if cursor.fetchone()[0] == 0:
                self.conn.execute(
                    'INSERT INTO article (category, is_topics, url, published_date, title, body) VALUES (?, ?, ?, ?, ?, ?)',
                    (category, is_topics, url, published_date, title, body)
                )
                success = True
            else:
                success = False

            self.conn.commit()

        except Exception as e:
            print(f"Error inserting article: {e}")
            success = False

        finally:
            self.close()
        
        return success

    def is_url_in_db(self, url):
        try:
            self.connect()
            cursor = self.conn.execute('SELECT COUNT(*) FROM article WHERE url=?', (url,))
            if cursor.fetchone()[0] == 1:
                return True
            return False

        except:
            return False

        finally:
            self.close()

    def get_max_id(self, category: str=None) -> int:
        """get max id of the article 

        Args:
            category (str, optional): category of the article. Defaults to None.

        Returns:
            int: max id of the article for the category if category is specified, otherwise max id of the article for all categories.
        """
        
        try:
            self.connect()
            category_condition = f"WHERE category = '{category}'" if category else ""
            cursor = self.conn.execute(f'SELECT MAX(id) FROM article {category_condition}')
            max_id = cursor.fetchone()[0]
            return max_id
        finally:
            self.close()

    def get_article_count(self, max_id: int, category: str=None):
        try:
            self.connect()
            category_condition = f"AND category = '{category}'" if category else ""
            cursor = self.conn.execute(f'SELECT COUNT(*) FROM article WHERE id < {max_id} {category_condition}')
            count = cursor.fetchone()[0]
            return count
        finally:
            self.close()

    def get_article(self, max_id, i, category=None):
        try:
            self.connect()
            category_condition = f"category = '{category}' AND" if category else ""
            sql = f'''
                SELECT * FROM article
                WHERE {category_condition} id < {max_id}
                ORDER BY published_date DESC
                LIMIT 1 OFFSET {i-1}
            '''
            article = self.conn.execute(sql).fetchone()
            
            if article:
                id, category, is_topics, url, published_date, title, body = article
                result = {
                    'id': id,
                    'category': category,
                    'is_topics': is_topics,
                    'url': url,
                    'published_date': published_date,
                    'title': title,
                    'body': body
                }
            else:
                result = None
            
            return result

        except Exception as e:
            print(f"Error getting article: {e}")
            return None

        finally:
            self.close()


    def update_db(self, rss_url_list=[
        "https://news.yahoo.co.jp/rss/topics/top-picks.xml",
        "https://news.yahoo.co.jp/rss/topics/domestic.xml",
        "https://news.yahoo.co.jp/rss/topics/world.xml",
        "https://news.yahoo.co.jp/rss/topics/business.xml",
        "https://news.yahoo.co.jp/rss/topics/entertainment.xml",
        "https://news.yahoo.co.jp/rss/topics/sports.xml",
        "https://news.yahoo.co.jp/rss/topics/it.xml",
        "https://news.yahoo.co.jp/rss/topics/science.xml",
        "https://news.yahoo.co.jp/rss/topics/local.xml",
        "https://news.yahoo.co.jp/rss/categories/domestic.xml",
        "https://news.yahoo.co.jp/rss/categories/world.xml",
        "https://news.yahoo.co.jp/rss/categories/business.xml",
        "https://news.yahoo.co.jp/rss/categories/entertainment.xml",
        "https://news.yahoo.co.jp/rss/categories/sports.xml",
        "https://news.yahoo.co.jp/rss/categories/it.xml",
        "https://news.yahoo.co.jp/rss/categories/science.xml",
        "https://news.yahoo.co.jp/rss/categories/local.xml",
    ]):
        for rss_url in rss_url_list:
            category, _ = os.path.splitext(os.path.basename(rss_url))
            is_topics = 1 if "topics" in rss_url else 0
            articles = self.get_yahoo_news_by_rss(rss_url, category, is_topics)
            for article in articles:
                status = self.insert_article(
                                category, 
                                is_topics,
                                article["url"],
                                article["published_date"],
                                article["title"],
                                article["body"])
                # print(f"{status} ({article['title']})")

    def get_full_article_url(self, url):
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        full_article_link = soup.find("a", class_="sc-eQakvG")
        if full_article_link is None:
            return None
        return full_article_link["href"]

    def get_article_content(self, url):
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        article_title = soup.find("h1", class_="sc-keVrkP").text
        article_body = soup.find("div", class_="article_body").text
        return article_title, article_body

    def get_yahoo_news_by_rss(self, rss_url, category, is_topics, conn=None):
        if is_topics == 0:
            print(f"Retrieving articles in {category}")
        else:
            print(f"Retrieving articles in {category} (topics)")

        feed = feedparser.parse(rss_url)
        entries = feed.entries
        n_entries = len(entries)        

        print(f"{n_entries} articles found")

        news = []
        pbar = tqdm(entries)
        for entry in pbar:        
            full_article_url = self.get_full_article_url(entry.link)
            if full_article_url is None:
                full_article_url = entry.link
            if self.is_url_in_db(full_article_url):
                pbar.set_description("SKIP")
                continue
            try:
                title, body = self.get_article_content(full_article_url)
                published_date_dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                published_date = published_date_dt.strftime('%Y-%m-%d %H:%M:%S.%f')
                # print(f"Title: {title}\n\n{body}\n{'-'*80}\n")
                news.append({'title': title, 'body': body, 'url': full_article_url, 'published_date': published_date})
                pbar.set_description(f"{title[:10]}...")
            except Exception as e:
                traceback_str = traceback.format_exc()
                print(traceback_str)            
        return news

if __name__ == "__main__":
    db = NewsDatabase()
    db.update_db()
