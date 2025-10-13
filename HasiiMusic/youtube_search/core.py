import requests
from bs4 import BeautifulSoup

def search_youtube(query, max_results=10):
    url = f"https://www.youtube.com/results?search_query={query}"
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/85.0.4183.102 Safari/537.36'
        )
    }
    response = requests.get(url, headers=headers)
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
    if not results:
        print("No videos found. Try changing the search term or check your internet connection.")
    else:
        for video in results:
            print(video['title'], video['url'])
