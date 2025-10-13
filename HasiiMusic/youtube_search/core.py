import requests
from bs4 import BeautifulSoup

def search_youtube(query, max_results=10):
    url = f"https://www.youtube.com/results?search_query={query}"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    videos = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/watch?v=' in href:
            title = a.text.strip()
            if title:
                videos.append({
                    'title': title,
                    'url': f'https://www.youtube.com{href}'
                })
            if len(videos) == max_results:
                break
    return videos

if __name__ == "__main__":
    results = search_youtube("telegram music bot")
    for video in results:
        print(video['title'], video['url'])
