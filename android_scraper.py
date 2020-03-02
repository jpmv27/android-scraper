#!/usr/bin/env python3

'''
Scrape complete Android documentation site to PDF
'''

import argparse
import os
import resource
import subprocess
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

    subprocess.run(('google-chrome', '--headless', '--print-to-pdf=' + \
            file_name, url), stderr=subprocess.DEVNULL, check=True)


def url_to_filename(url):
    '''
    Convert URL to filename
    '''

    name = url[url.find('//') + 2:]

    for char in '"!/. ?=:\'':
        name = name.replace(char, '_')

    return name


class PdfOutput:
    '''
    Save URLs to PDF and accumulate into one output file
    '''

    class Bookmark:
        '''
        Represents a bookmark for a heading
        '''

        def __init__(self, title):
            self.title = title
            self.pdf_ref = None

        def get_ref(self):
            '''
            Return the bookmark reference
            '''

            return self.pdf_ref

        def is_pending(self):
            '''
            Check whether the bookmark has been added or not
            '''

            return self.pdf_ref is None

        def set_ref(self, ref):
            '''
            Update the bookmark reference
            '''

            self.pdf_ref = ref

    def __init__(self, file_name, *, delay=1, debug=False):
        self.file_name = file_name
        self.delay = delay
        self.debug = debug
        self.writer = PdfFileWriter()
        self.files_to_clean_up = []
        self.bookmark_stack = []

    def add_page(self, url, bookmark_title, *, bookmark=True):
        '''
        Add the URL to the PDF
        '''

        if url.endswith('.pdf'):
            return

        time.sleep(self.delay)

        file_name = self.make_unique_filename_ext(url_to_filename(url), '.pdf')

        if self.debug:
            print('Saving ' + url + ' to ' + file_name)
        else:
            save_url_to_pdf(url, file_name)

            page_index = self.writer.getNumPages()

            self.append_pdf_to_output(file_name)

            self.create_pending_bookmarks(page_index)

            if bookmark:
                self.bookmark_page(bookmark_title, page_index)

    def append_pdf_to_output(self, file_name):
        '''
        Append the PDF file to the output, remember file to clean up
        '''

        input_file = open(file_name, 'rb')
        input_stream = PdfFileReader(input_file)
        self.writer.appendPagesFromReader(input_stream)

        self.files_to_clean_up.append(file_name)

    def bookmark_page(self, title, page_num):
        '''
        Bookmark the page
        '''

        parent = None
        if self.bookmark_stack:
            parent = self.bookmark_stack[-1].get_ref()

        self.writer.addBookmark(title, page_num, parent=parent)

    def clean_up_files(self):
        '''
        Delete all the files to be cleaned-up
        '''

        for file in self.files_to_clean_up:
            os.remove(file)

    def create_pending_bookmarks(self, page_num):
        '''
        Create heading bookmarks that have not yet been created
        '''

        parent = None

        for bookmark in self.bookmark_stack:
            if bookmark.is_pending():
                bookmark.set_ref(self.writer.addBookmark( \
                        bookmark.title, page_num, parent=parent))
            parent = bookmark.get_ref()

    def finish(self):
        '''
        Wrap-up processing by writing the output file and cleaning-up
        '''

        self.write_output()
        self.clean_up_files()

    def make_unique_filename_ext(self, file_name, ext):
        '''
        Check a file name and extension for uniqueness and append
        a suffix if necessary to make it unique
        '''

        suffix = 2

        tentative_name = file_name

        while tentative_name + ext in self.files_to_clean_up:
            tentative_name = file_name + str(suffix)
            suffix += 1

        return tentative_name + ext

    def pop_heading(self):
        '''
        Outdent subsequent bookmarks
        '''

        self.bookmark_stack.pop()

    def push_heading(self, bookmark_title):
        '''
        Add a heading and make subsequent bookmarks a child of
        this heading
        '''

        self.bookmark_stack.append(self.Bookmark(bookmark_title))

    def write_output(self):
        '''
        Generate the output file
        '''

        output_file = open(self.file_name, 'wb')
        self.writer.write(output_file)
        output_file.close()


def title_to_bookmark_title(title):
    '''
    Extract the bookmark name from a page title
    '''

    vertical_bar = title.find('|')
    if not vertical_bar:
        return title

    return title[:vertical_bar - 1].strip()


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

    if 'devsite-nav-heading' in item['class']:
        # TODO
        return

    if 'devsite-nav-expandable' in item['class']:
        nav_text = item.select_one('span.devsite-nav-text')
        output.push_heading(nav_text.text.strip())
        for subitem in item.find('ul').find_all('li', recursive=False):
            scrape_side_menu_item(site_url, subitem, output)
        output.pop_heading()
        return

    a_tag = item.find('a')

    output.add_page(url_to_absolute(site_url, a_tag['href']), \
            a_tag.text.strip())


def scrape_lower_tab(site_url, tab, output):
    '''
    Scrape a minor section, represented by a lower tab

    Iterate through the chapters in the side menu, or save the lower
    tab page if there is no side menu. Side menu items may be nested
    '''

    a_tag = tab.find('a')
    tab_url = a_tag['href']

    page = read_page(url_to_absolute(site_url, tab_url))

    tag = page.select_one('nav.devsite-book-nav')

    if tag:
        side_menu = tag.select_one('ul.devsite-nav-list[menu="_book"]')
    else:
        side_menu = None

    if side_menu:
        output.push_heading(a_tag.text.strip())
        for item in side_menu.find_all('li', recursive=False):
            scrape_side_menu_item(site_url, item, output)
        output.pop_heading()
        return

    output.add_page(url_to_absolute(site_url, tab_url), \
            title_to_bookmark_title(page.title.string))


def scrape_upper_tab(site_url, tab, output):
    '''
    Scrape a major section, represented by an upper tab

    Iterate through all the lower tabs, or save the upper tab page
    if there are no lower tabs
    '''

    a_tag = tab.find('a')
    tab_url = a_tag['href']

    page = read_page(url_to_absolute(site_url, tab_url))

    lower_tabs = page.select_one('devsite-tabs.lower-tabs')

    if lower_tabs:
        output.push_heading(a_tag.text.strip())
        for lower_tab in lower_tabs.find_all('tab'):
            scrape_lower_tab(site_url, lower_tab, output)
        output.pop_heading()
        return

    output.add_page(url_to_absolute(site_url, tab_url), \
            title_to_bookmark_title(page.title.string))


def scrape_site(url, output):
    '''
    Scrape the site

    Save the site main page, then iterate through all the upper tabs
    '''

    page = read_page(url)

    output.push_heading(page.title.string.strip())

    output.add_page(url, url, bookmark=False)

    for tag in page.select('devsite-tabs.upper-tabs'):
        for tab in tag.find_all('tab'):
            scrape_upper_tab(url, tab, output)

    output.pop_heading()

def parse_command_line():
    '''
    Parse the command line and save options
    '''

    parser = argparse.ArgumentParser('Scrape an android.com site to PDF')
    parser.add_argument('url', type=str, metavar='URL')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--delay', type=int, default=1, \
            metavar='DELAY', help='Delay in seconds between requests')
    parser.add_argument('-o', '--output', type=str, metavar='OUTPUT', \
            default='scraper.pdf', help='Output file name')

    return parser.parse_args()


def main():
    '''
    Parse arguments and perform scraping
    '''

    try:
        args = parse_command_line()

        output = PdfOutput(args.output, debug=args.debug, delay=args.delay)

        # developer.android.com causes "too many open files" error
        resource.setrlimit(resource.RLIMIT_NOFILE, (10000, 10000))

        scrape_site(args.url, output)

        output.finish()

        print('Done')

    except KeyboardInterrupt:
        print('Cancelled')

main()
