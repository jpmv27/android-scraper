#!/usr/bin/env python3

'''
Scrape complete Android documentation site to PDF
'''

import argparse
import os
import time

from bs4 import BeautifulSoup as bs
import requests

# Use html5lib because html.parser makes a mess of malformed HTML
PARSER = 'html5lib'

class Options: # pylint: disable=too-few-public-methods
    '''
    Options
    '''

    delay = 1
    debug = False
    recover = False


def url_to_filename(url, extension):
    '''
    Convert URL to filename
    '''

    name = url[url.find('//') + 2:]

    for char in '"!/. \'':
        name = name.replace(char, '_')

    return name + extension


def save_to_pdf(url):
    '''
    Save the URL to a PDF
    '''

    if url.endswith('.pdf'):
        return

    time.sleep(Options.delay)

    file_name = url_to_filename(url, '.pdf')

    if Options.recover and \
            os.path.exists(file_name):
        print('Skipping ' + url)
        return

    if Options.debug:
        print('Saving ' + url + ' to ' + file_name)
    else:
        os.system('google-chrome --headless --print-to-pdf=' + \
                file_name + ' ' + url + ' 2> /dev/null')


def url_to_absolute(site_url, page_url):
    '''
    Resolve page URL to absolute URL if relative
    '''

    if page_url.startswith('http'):
        return page_url

    return site_url + page_url


def scrape_lower_tab(site_url, tab_url):
    '''
    Scrape a minor section, represented by a lower tab
    '''

    response = requests.get(url_to_absolute(site_url, tab_url))
    response.raise_for_status()

    doc = bs(response.text, PARSER)

    tag = doc.select_one('nav.devsite-book-nav')
    if tag:
        inner_tag = tag.select_one('ul.devsite-nav-list[menu="_book"]')
    else:
        inner_tag = None

    if not inner_tag:
        save_to_pdf(url_to_absolute(site_url, tab_url))
    else:
        for item in inner_tag.find_all('li'):
            if 'devsite-nav-expandable' not in item['class']:
                a_tag = item.find('a')
                if a_tag:
                    save_to_pdf(url_to_absolute(site_url, a_tag['href']))


def scrape_upper_tab(site_url, tab_url):
    '''
    Scrape a major section, represented by an upper tab
    '''

    response = requests.get(url_to_absolute(site_url, tab_url))
    response.raise_for_status()

    doc = bs(response.text, PARSER)

    lower_tabs = doc.select_one('devsite-tabs.lower-tabs')
    if not lower_tabs:
        save_to_pdf(url_to_absolute(site_url, tab_url))
    else:
        for tab in lower_tabs.find_all('tab'):
            scrape_lower_tab(site_url, tab.find('a')['href'])


def scrape_site(url):
    '''
    Scrape the site
    '''

    save_to_pdf(url)

    response = requests.get(url)
    response.raise_for_status()

    doc = bs(response.text, PARSER)

    for tag in doc.select('devsite-tabs.upper-tabs'):
        for tab in tag.find_all('tab'):
            scrape_upper_tab(url, tab.find('a')['href'])


def main():
    '''
    Parse arguments and initiate scraping
    '''

    try:
        parser = argparse.ArgumentParser('Scrape an android.com site to PDF')
        parser.add_argument('url', type=str, metavar='URL')
        parser.add_argument('--debug', action='store_true')
        parser.add_argument('--delay', type=int, default=1, \
                metavar='DELAY', help='Delay in seconds between requests')
        parser.add_argument('--recover', action='store_true', \
                help='Recover from a previously interrupted session')
        args = parser.parse_args()

        Options.debug = args.debug
        Options.delay = args.delay
        Options.recover = args.recover

        scrape_site(args.url)

        print('done')
    except KeyboardInterrupt:
        print('cancelled')

main()
