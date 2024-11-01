import requests
from bs4 import BeautifulSoup
import json
import openai
from collections import deque
import re  

# open ai key for table formating
openai.api_key = 'your_openai_api_key'

#ollama url for local test
ollama_url = "http://127.0.0.1:11434/api/generate"

domain = 'https://www.notion.com'
url_queue = deque(['/help'])  # start URL

# avoid duplicate processing
url_scraped = set()  

    
# remove emojis in text
emoji_pattern = re.compile(  
    "["  
    "\U0001F600-\U0001F64F"  # emoticons  
    "\U0001F300-\U0001F5FF"  # symbols & pictographs  
    "\U0001F680-\U0001F6FF"  # transport & map symbols  
    "\U0001F700-\U0001F77F"  # alchemical symbols  
    "\U0001F780-\U0001F7FF"  # geometric shapes  
    "\U0001F800-\U0001F8FF"  # supplemental arrows  
    "\U0001F900-\U0001F9FF"  # supplemental symbols and pictographs  
    "\U0001FA00-\U0001FA6F"  # chess symbols  
    "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended  
    "\U00002600-\U000026FF"  # miscellaneous symbols  
    "\U00002700-\U000027BF"  # dingbats  
    "]+",  
    re.UNICODE  
)
  
def remove_emojis(text):  
    # 使用正则表达式替换匹配到的表情符号为空字符串  
    return emoji_pattern.sub("", text)  

# fetch content of url
def fetch_page(url):
    response = requests.get(url)
    return response.text

# get all links that start with /help/ in a page
def parse_content(page_html):
    soup = BeautifulSoup(page_html, 'html.parser')
    links = []

    main_html = soup.find('main') # we only use content in main tag
    main_html.find('aside').decompose () # remove unused aside tag

    #parse links
    for link in soup.find_all('a', href=True):
        if link['href'] and link['href'].startswith('/help/' ):
            links.append(link['href'])
    return main_html, links

def split_into_chunks(soup, max_chunk_size=750):
    chunks = []
    current_chunk = ""
    in_list_or_table = False
    list_level = 0

    def add_to_chunk(text):
        text = remove_emojis(text)
        nonlocal current_chunk
        if len(current_chunk) + len(text) <= max_chunk_size: 
            current_chunk += "\n" + text
        else:
            chunks.append(current_chunk.strip())
            current_chunk = text
    
    def traverse_elements(element, level=0):
        if not element:
            return
        nonlocal in_list_or_table
        nonlocal list_level
        if isinstance(element, str):
            add_to_chunk(element.strip())
        else:
            if in_list_or_table:
                if  level > list_level :
                    # list and table content have already been added, skip 
                    return
                else:
                    # list or table over, new tag comes
                    list_level = 0
                    in_list_or_table = False

            # ul ol and table content should not be splited into different chunk
            if element.name in ['ul','ol','table']:
                text = element.get_text(separator='\n', strip=True)
                if element.name == "table":
                    # format table content by ai
                    text = format_table_with_openai(text)
                add_to_chunk(text)

                list_level = level
                in_list_or_table = True
                return
            else: 
                for child in element.children:
                    traverse_elements(child, level + 1)
    traverse_elements(soup)

    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

# format text by openai
def format_table_with_openai(text):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a text formatter. Your job is to take the given text and make it more readable and well-formatted."},
            {"role": "user", "content": text},
        ]
    )
    formatted_text = response.choices[0].message.content
    return formatted_text

# format text by ollama, for local test
def format_table_with_ollama(text):
    # 构建请求数据
    data = {
        "prompt" : "Please make the following text more readable and well-formatted, give me only one anwser directly and no extra text: %s" % text,
        "model":"gemma2:27b",
        "stream":False,
    }

    # 发送 POST 请求
    response = requests.post(ollama_url, json=data)
    # print(data)

    # 检查请求是否成功
    if response.status_code == 200:
        result = response.json()
        # print(result)
        generated_text = result.get('response', '')
        return generated_text
    else:
        return text

def scrape_url(link):
    url = "%s%s" % (domain,link)
    print("scrape_url",url)
    page_html = fetch_page(url)
    main_html,page_links = parse_content(page_html)

    for link in page_links:
        if link not in url_scraped:
            url_queue.append(link)

    chunks = split_into_chunks(main_html)

    for index,item in enumerate(chunks):
        print(index+1)
        print(item)
        print()
        
def main():
    while url_queue:
        current_link = url_queue.popleft()
        if current_link not in url_scraped:
            url_scraped.add(current_link)
            scrape_url(current_link)

if __name__ == '__main__':
    main()
