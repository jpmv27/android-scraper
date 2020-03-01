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


def read_page(url):
    '''
    Read page at URL
    '''

    response = requests.get(url)
    response.raise_for_status()

    return bs(response.text, PARSER)


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
        return None

    time.sleep(Options.delay)

    file_name = url_to_filename(url, '.pdf')

    if Options.recover and \
            os.path.exists(file_name):
        return file_name

    if Options.debug:
        print('Saving ' + url + ' to ' + file_name)
    else:
        os.system('google-chrome --headless --print-to-pdf=' + \
                file_name + ' ' + url + ' 2> /dev/null')

    return file_name


def url_to_absolute(site_url, page_url):
    '''
    Resolve page URL to absolute URL if relative
    '''

    if page_url.startswith('http'):
        return page_url

    return site_url + page_url


def scrape_side_menu_item(site_url, item):
    '''
    Scrape a chapter with sub-chapters, represented by an expandable
    side menu item

    Iterate through the chapters in the item, or save the item if
    there are no sub-items
    '''

    if 'devsite-nav-expandable' in item['class']:
        for subitem in item.find('ul').find_all('li', recursive=False):
            scrape_side_menu_item(site_url, subitem)
        return

    # Sometimes the item doesn't really exist
    a_tag = item.find('a')

    if a_tag:
        save_to_pdf(url_to_absolute(site_url, a_tag['href']))


def scrape_lower_tab(site_url, tab_url):
    '''
    Scrape a minor section, represented by a lower tab

    Iterate through the chapters in the side menu, or save the lower
    tab page if there is no side menu. Side menu items may be nested
    '''

    page = read_page(url_to_absolute(site_url, tab_url))

    tag = page.select_one('nav.devsite-book-nav')

    if tag:
        side_menu = tag.select_one('ul.devsite-nav-list[menu="_book"]')
    else:
        side_menu = None

    if side_menu:
        for item in side_menu.find_all('li', recursive=False):
            scrape_side_menu_item(site_url, item)
        return

    save_to_pdf(url_to_absolute(site_url, tab_url))


def scrape_upper_tab(site_url, tab_url):
    '''
    Scrape a major section, represented by an upper tab

    Iterate through all the lower tabs, or save the upper tab page
    if there are no lower tabs
    '''

    page = read_page(url_to_absolute(site_url, tab_url))

    lower_tabs = page.select_one('devsite-tabs.lower-tabs')

    if lower_tabs:
        for tab in lower_tabs.find_all('tab'):
            scrape_lower_tab(site_url, tab.find('a')['href'])
        return

    save_to_pdf(url_to_absolute(site_url, tab_url))


def scrape_site(url):
    '''
    Scrape the site

    Save the site main page, then iterate through all the upper tabs
    '''

    save_to_pdf(url)

    page = read_page(url)

    for tag in page.select('devsite-tabs.upper-tabs'):
        for tab in tag.find_all('tab'):
            scrape_upper_tab(url, tab.find('a')['href'])


def parse_command_line():
    '''
    Parse the command line and save options
    '''

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

    return args.url


def main():
    '''
    Parse arguments and perform scraping
    '''

    try:
        url = parse_command_line()

        scrape_site(url)

        print('Done')

    except KeyboardInterrupt:
        print('Cancelled')

main()
