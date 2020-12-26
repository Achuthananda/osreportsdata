from urllib.request import urlopen
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin


# get the JavaScript files
def getBasePageUrl(url):
    all_urls = []
    html = urlopen(url)
    soup = BeautifulSoup(html, 'html.parser')

    for script in soup.find_all("script"):
        if script.attrs.get("src"):
            # if the tag has the attribute 'src'
            script_url = urljoin(url, script.attrs.get("src"))
            if url in script_url:
                all_urls.append(script_url)

    # get the CSS files
    css_files = []
    for css in soup.find_all("link"):
        if css.attrs.get("href"):
            # if the link tag has the 'href' attribute
            css_url = urljoin(url, css.attrs.get("href"))
            if url in css_url:
                all_urls.append(css_url)


    images_files = []
    for img in soup.find_all("img"):
        if img.attrs.get("src"):
            # if the link tag has the 'href' attribute
            img_url = urljoin(url, img.attrs.get("src"))
            if url in img_url:
                all_urls.append(img_url)


    all_urls = set(all_urls)
    #print(len(all_urls))
    #print(all_urls)
    return all_urls
