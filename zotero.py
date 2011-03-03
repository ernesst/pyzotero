#!/usr/bin/env python
# encoding: utf-8
"""
zotero.py

Created by Stephan Hügel on 2011-02-28
Copyright Stephan Hügel, 2011

License: http://www.gnu.org/licenses/gpl-3.0.txt
"""

__version__ = '0.1'

import sys
import os
import urllib
import urllib2
import feedparser
import xml.etree.ElementTree as xml



# Define some exceptions
class PyZoteroError(Exception):
    """ Generic parent exception
    """
    pass



class ParamNotPassed(PyZoteroError):
    """ Raised if a parameter which is required isn't passed
    """
    pass



class CallDoesNotExist(PyZoteroError):
    """ Raised if the specified API call doesn't exist
    """
    pass



def open_file(to_read):
    """ Open a text file for reading, and strip the newlines
        returns a list, one list item per line
    """
    try:
        with open(to_read, 'r') as opened:
            return [got_lines.rstrip('\n') for got_lines in opened.readlines()]
    except IOError:
        print "Couldn't read values from %s\nCan't continue." % to_read
        raise


def item_data(fp_object):
    """ Takes the result of a parse operation, and returns a list containing
        one or more dicts containing item data
    """
    # Shunt each 'content' block into a list
    item_parsed = [a['content'][0]['value'] for a in fp_object.entries]
    # Shunt each 'title' and item ID value into a list
    item_title = [t['title'] for t in fp_object.entries]
    item_id = [i['zapi_key'] for i in fp_object.entries]
    items = []
    for index, content in enumerate(item_parsed):
        elem = xml.fromstring(content.encode('utf-8'))
        keys = [e.text for e in elem.iter('th')]
        values = [v.text for v in elem.iter('td')]
        zipped = dict(zip(keys, values))
        # add the utf-8 encoded 'title' and ID data to the dict:
        zipped['Title'] = item_title[index].encode('utf-8')
        zipped['ID'] = item_id[index].encode('utf-8')
        items.append(zipped)
    return items


def gen_item_data(fp_object):
    """ Returns a generator object containing one or more dicts of item data
    """
    # Shunt each 'content' block into a list
    item_parsed = [a['content'][0]['value'] for a in fp_object.entries]
    # Shunt each 'title' and item ID value into a list
    item_title = [t['title'] for t in fp_object.entries]
    item_id = [i['zapi_key'] for i in fp_object.entries]
    items = []
    for index, content in enumerate(item_parsed):
        elem = xml.fromstring(content.encode('utf-8'))
        keys = [e.text for e in elem.iter('th')]
        values = [v.text for v in elem.iter('td')]
        zipped = dict(zip(keys, values))
        # add the utf-8 encoded 'title' and ID data to the dict:
        zipped['Title'] = item_title[index].encode('utf-8')
        zipped['ID'] = item_id[index].encode('utf-8')
        items.append(zipped)
    gen_items = (i for i in items)
    return gen_items


def collections_data(fp_object):
    """ Takes the result of a parse operation, and returns a list containing
        one or more dicts containing collection titles and IDs
    """
    collections = []
    collection_key = [k['zapi_key'] for k in fp_object.entries]
    collection_title = [t['title'] for t in fp_object.entries]
    collection_sub = [s['zapi_numcollections'] for s in fp_object.entries]
    for index, content in enumerate(collection_key):
        collection_data = {}
        collection_data['ID'] = collection_key[index].encode('utf-8')
        collection_data['title'] = collection_title[index].encode('utf-8')
        if int(collection_sub[index]) > 0:
            collection_data['subcollections'] = int(collection_sub[index])
        collections.append(collection_data)
    return collections



class Zotero(object):
    """ Zotero API methods
        A full list of methods can be found here:
        http://www.zotero.org/support/dev/server_api
        Most of the methods return Atom feed documents, which can be parsed
        using feedparser (http://www.feedparser.org/docs/)

        Valid optional URL parameters for all calls: ('key' added by default)
        format: "atom" or "bib", default: "atom"
        version: integer, default: null

        Valid optional URL parameters for format=atom:
        content: "none", "html", "bib", default: "html"
        order: string, name of field to be used, default: "dateAdded"
        sort: "asc", "desc", default varies by "order"
        limit: integer 1 - 99, default 50
        start: integer, default: 0
        pprint: boolean, default: false
    """
    user_id = None
    user_key = None
    
    def __init__(self, user_id = None, user_key = None):
        """ Store Zotero credentials
        """
        self.endpoint = 'https://api.zotero.org'
        if user_id and user_key:
            self.user_id = user_id
            self.user_key = user_key
        # API methods
        self.api_methods = {
        'all_items':'/users/{u}/items',
        'top_level_items':'/users/{u}/items/top',
        'specific_item':'/users/{u}/items/{item}',
        'child_items':'/users/{u}/items/{item}/children',
        'item_tags':'/users/{u}/items/{item}/tags',
        'user_tags':'/users/{u}/tags',
        'items_for_tag':'/users/{u}/tags/{tag}/items',
        'collections':'/users/{u}/collections',
        'collection_items':'/users/{u}/collections/{collection}',
        'sub_collections': '/users/{u}/collections/{collection}/collections',
        'user_groups': '/users/{u}/groups',
        'group_items':'/groups/{group}/items',
        'top_group_items': '/groups/{groupID}/items/top',
        'group_item': '/groups/{group}/items/{item}',
        'group_item_children': '/groups/{groupID}/items/{item}/children',
        'group_item_tags': '/groups/{group}/items/{item}/tags',
        'group_tags': '/groups/{group}/tags',
        'group_user_items_tag': '/groups/{group}/tags/{tag}/items',
        'group_collections': '/groups/{groupID}/collections',
        'group_collection': '/groups/{group}/collections/{collection}',
        'group_collection_sub': '/groups/{group}/collections/{collection}/collections',
        'group_collection_items': '/groups/{group}/collections/{collection}/items',
        'group_collection_item': '/groups/{group}/collections/{collection}/items/{item}'
        }

    def total_items(self):
        """ Return the total number of items in the library
        """
        get_count = self.retrieve_data('top_level_items', {'limit': 1})
        return get_count.feed['zapi_totalresults'].decode('utf-8')

    def retrieve_data(self,
        request, url_params = None, request_params = None):
        """ Method for retrieving Zotero items via the API
            returns a dict containing feed items and lists of entries
        """
        # Add request parameter(s) if required
        if request not in self.api_methods:
            raise CallDoesNotExist
        if request_params:
            try:
                request_params['u'] = self.user_id
                request = urllib.quote(
                self.api_methods[request].format(**request_params))
            except KeyError:
                print 'There\'s a request parameter missing:'
                raise ParamNotPassed
        # Otherwise, just add the user ID
        else:
            try:
                request = self.api_methods[request].format(u = self.user_id)
            except KeyError:
                print 'There\'s a request parameter missing:'
                raise ParamNotPassed
        # Add URL parameters if they're passed
        if url_params:
            url_params['key'] = self.user_key
            data = urllib.urlencode(url_params)
        # Otherwise, just add the user key
        else:
            url_params = {'key': self.user_key}
            data = urllib.urlencode(url_params)
        request = '%s%s%s' % (request, '?', data)
        full_url = '%s%s' % (self.endpoint, request)
        data = urllib2.urlopen(full_url).read()
        # parse the result into Python data structures
        return feedparser.parse(data)



def main():
    """ main function
    """
    # Read a file from your cwd. Expects user id on line 1, key on line 2, LF
    auth_values = open_file(os.path.join(os.path.expanduser('~'),
    'zotero_keys.txt'))
    zot_id = auth_values[0]
    zot_key = auth_values[1]
    zot = Zotero(zot_id, zot_key)
    # Pass optional request parameters in a dict
    # req = {'item': 'T4AH4RZA'}
    par = {'limit': 5}
    item = zot.retrieve_data('top_level_items', par)
    # We can now do whatever we like with the returned data, e.g.:
    # We can pass our feedparser object to a helper function
    print item_data(item)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        # actually raise these, for a clean exit
        raise
    except Exception, error:
        # all other exceptions: display the error
        print error
        # print "Stack trace:\n", traceback.print_exc(file = sys.stdout)
    else:
        pass
    finally:
        # exit cleanly once we've done everything else
        sys.exit(0)