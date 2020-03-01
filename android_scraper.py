#!/usr/bin/env python3

'''
Scrape complete Android documentation site to PDF
'''

import argparse
import os
import sys
import time

from bs4 import BeautifulSoup as bs
from PyPDF2 import PdfFileReader, PdfFileWriter
import requests

# Use html5lib because html.parser makes a mess of malformed HTML
PARSER = 'html5lib'


def save_url_to_pdf(url, file_name):
    '''
    Save the URL to the specified PDF file
    '''

    os.system('google-chrome --headless --print-to-pdf=' + \
            file_name + ' ' + url + ' 2> /dev/null')


def url_to_filename(url, extension):
    '''
    Convert URL to filename
    '''

    name = url[url.find('//') + 2:]

    for char in '"!/. \'':
        name = name.replace(char, '_')

    return name + extension


class PdfOutput:
    '''
    Save URLs to PDF and accumulate into one output file
    '''

    def __init__(self, file_name, *, delay=1, debug=False):
        self.file_name = file_name
        self.delay = delay
        self.debug = debug
        self.writer = PdfFileWriter()
        self.files_to_clean_up = []

    def add(self, url):
        '''
        Add the URL to the PDF
        '''

        if url.endswith('.pdf'):
            return

        time.sleep(self.delay)

        file_name = url_to_filename(url, '.pdf')

        if self.debug:
            print('Saving ' + url + ' to ' + file_name)
        else:
            save_url_to_pdf(url, file_name)

            num_pages = self.writer.getNumPages()
            self.append_pdf_to_output(file_name)

            self.writer.addBookmark(file_name, num_pages)
            num_pages = self.writer.getNumPages()
            print('now have ' + str(num_pages) + ' pages')
            if num_pages > 100:
                self.finish()
                sys.exit(0)

    def append_pdf_to_output(self, file_name):
        '''
        Append the PDF file to the output, remember file to clean up
        '''

        input_file = open(file_name, 'rb')
        input_stream = PdfFileReader(input_file)
        self.writer.appendPagesFromReader(input_stream)

        self.files_to_clean_up.append(file_name)

    def clean_up_files(self):
        '''
        Delete all the files to be cleaned-up
        '''

        for file in self.files_to_clean_up:
            os.remove(file)

    def finish(self):
        '''
        Wrap-up processing by writing the output file and cleaning-up
        '''

        self.write_output()
        self.clean_up_files()

    def write_output(self):
        '''
        Generate the output file
        '''

        output_file = open(self.file_name, 'wb')
        self.writer.write(output_file)
        output_file.close()


def read_page(url):
    '''
    Read page at URL
    '''

    response = requests.get(url)
    response.raise_for_status()

    return bs(response.text, PARSER)


def url_to_absolute(site_url, page_url):
    '''
    Resolve page URL to absolute URL if relative
    '''

    if page_url.startswith('http'):
        return page_url

    return site_url + page_url


def scrape_side_menu_item(site_url, item, output):
    '''
    Scrape a chapter with sub-chapters, represented by an expandable
    side menu item

    Iterate through the chapters in the item, or save the item if
    there are no sub-items
    '''

    if 'devsite-nav-expandable' in item['class']:
        for subitem in item.find('ul').find_all('li', recursive=False):
            scrape_side_menu_item(site_url, subitem, output)
        return

    # Sometimes the item doesn't really exist
    a_tag = item.find('a')

    if a_tag:
        output.add(url_to_absolute(site_url, a_tag['href']))


def scrape_lower_tab(site_url, tab_url, output):
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
            scrape_side_menu_item(site_url, item, output)
        return

    output.add(url_to_absolute(site_url, tab_url))


def scrape_upper_tab(site_url, tab_url, output):
    '''
    Scrape a major section, represented by an upper tab

    Iterate through all the lower tabs, or save the upper tab page
    if there are no lower tabs
    '''

    page = read_page(url_to_absolute(site_url, tab_url))

    lower_tabs = page.select_one('devsite-tabs.lower-tabs')

    if lower_tabs:
        for tab in lower_tabs.find_all('tab'):
            scrape_lower_tab(site_url, tab.find('a')['href'], output)
        return

    output.add(url_to_absolute(site_url, tab_url))


def scrape_site(url, output):
    '''
    Scrape the site

    Save the site main page, then iterate through all the upper tabs
    '''

    output.add(url)

    page = read_page(url)

    for tag in page.select('devsite-tabs.upper-tabs'):
        for tab in tag.find_all('tab'):
            scrape_upper_tab(url, tab.find('a')['href'], output)


def parse_command_line():
    '''
    Parse the command line and save options
    '''

    parser = argparse.ArgumentParser('Scrape an android.com site to PDF')
    parser.add_argument('url', type=str, metavar='URL')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--delay', type=int, default=1, \
            metavar='DELAY', help='Delay in seconds between requests')

    return parser.parse_args()


def main():
    '''
    Parse arguments and perform scraping
    '''

    try:
        args = parse_command_line()

        output = PdfOutput('scraper.pdf', debug=args.debug, delay=args.delay)

        scrape_site(args.url, output)

        output.finish()

        print('Done')

    except KeyboardInterrupt:
        print('Cancelled')

main()
