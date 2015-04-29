#! /usr/bin/env python

import sys
import json
import re
import logging
import argparse
import time
import datetime
import pprint
import numpy
from urlparse import urlparse
from collections import defaultdict

CACHEABLE_CATEGORIES = ('image', 'text', 'css', 'javascript', 'flash', 'pdf',\
                        'xml', 'json', 'audio', 'video', 'font')
CACHE_CONTROL_CACHEABLE = ('public', 'max-age', 's-maxage', 'must-revalidate',\
                           'proxy-revalidate', 'no-transform')
CACHE_CONTROL_NOT_CACHEABLE = ('private', 'no-cache', 'no-store')

class HarError(Exception):
    pass

class HarObject(object):
    '''Encapsulates a single HAR request'''

    def __init__(self, object_json):
        self.json = object_json

        def process_headers(headers):
            # FIXME: don't discard multiple headers of same type
            header_dict = {}
            for header in headers:
                if header['name'] in header_dict:
                    logging.getLogger(__name__)\
                        .debug('Header "%s" already exists in this response.',
                        header['name'])
                else:
                    header_dict[header['name']] = header['value']
            return header_dict

        # make dicts for request and response headers
        self.request_headers = process_headers(self.json['request']['headers'])
        self.response_headers = process_headers(self.json['response']['headers'])

    def sanity_check(self, print_report=True):
        report = ''
        safe = True

        if 'timings' not in self.json:
            report += '-> No timings object'
            safe = False

        if self.category == 'unknown' and self.mime_type != '':
            report += '-> Unknown MIME type: %s\n' % self.mime_type

        if self.category == 'unknown' and self.content_size > 0:
            report += '-> Object of unknown type %s has nonzero size %d' % (self.mime_type, self.content_size)

        if self.content_size - self.content_compression != self.body_size:
            report += '-> Body size (%d) does not match content size (%d) minus compression (%d)\n'\
                % (self.body_size, self.content_size, self.content_compresion)

        if report != '' and print_report:
            print '\n========== SANITY CHECK REPORT ==========\n'
            print report + '\n'
            print self.json

        return safe

        

    def _get_mime_type(self):
        return self.json['response']['content']['mimeType']
    mime_type = property(_get_mime_type)

    def _get_category(self):
        if 'image' in self.mime_type:
            return 'image'
        elif 'audio' in self.mime_type:
            return 'audio'
        elif 'video' in self.mime_type:
            return 'video'
        elif 'css' in self.mime_type:
            return 'css'
        elif 'html' in self.mime_type:
            return 'html'
        elif 'javascript' in self.mime_type:
            return 'javascript'
        elif any(t in self.mime_type for t in ['text/plain', 'text/rtf']):
            return 'text'
        elif 'flash' in self.mime_type:
            return 'flash'
        elif any(t in self.mime_type for t in ['text/xml', 'application/xml']):
            return 'xml'
        elif 'json' in self.mime_type:
            return 'json'
        elif 'font' in self.mime_type:
            return 'font'
        elif 'octet-stream' in self.mime_type:
            return 'binary'
        else:
            return 'unknown'
    category = property(_get_category)

    @property
    def url(self):
        return self.json['request']['url']

    @property
    def host(self):
        return urlparse(self.url).netloc

    @property
    def path(self):
        return urlparse(self.url).path

    @property
    def filename(self):
        return self.url.split('/')[-1]

    def _get_protocol(self):
        return self.url.split('://')[0]
    protocol = property(_get_protocol)

    @property
    def response_code(self):
        return int(self.json['response']['status'])

    @property
    def object_start_time(self):
        return datetime.datetime.strptime(\
            self.json['startedDateTime'], '%Y-%m-%dT%H:%M:%S.%fZ') 

    def _get_timings(self):
        return self.json['timings']
    timings = property(_get_timings)

    @property
    def request_headers_size(self):
        return int(self.json['request']['headersSize'])

    @property
    def request_body_size(self):
        return int(self.json['request']['bodySize'])

    @property
    def response_headers_size(self):
        return int(self.json['response']['headersSize'])

    @property
    def content_size(self):
        '''Size of original content (before compression)'''
        content_size = int(self.json['response']['content']['size'])
        return content_size

    @property
    def content_compression(self):
        '''Number of bytes saved by compression'''
        return int(self.json['response']['content']['compression'])

    def _get_body_size(self):
        '''Size of response body (possibly compressed)'''
        body_size = int(self.json['response']['bodySize'])
        return body_size
    response_body_size = property(_get_body_size)
    body_size = property(_get_body_size)

    def _get_explicitly_cacheable(self):
        '''Based on response headers, is this cacheable?'''
        try:
            if 'Expires' in self.response_headers:
                if self.response_headers['Expires'] in ['0', '-1']:
                    return False
                elif 'Date' in self.response_headers:
                    try:
                        expires = time.strptime(self.response_headers['Expires'][:-4].replace('-', ' '),\
                            '%a, %d %b %Y %H:%M:%S')
                        date = time.strptime(self.response_headers['Date'][:-4].replace('-', ' '),\
                            '%a, %d %b %Y %H:%M:%S')
                        return expires > date
                    except Exception as e:
                        logging.getLogger(__name__).warn('Error parsing date: %s', e)
                        pass
            elif 'Cache-Control' in self.response_headers:
                if any(t in self.response_headers['Cache-Control'] for t in CACHE_CONTROL_NOT_CACHEABLE):
                    return False
                elif 'max-age=' in self.response_headers['Cache-Control']:
                    max_age = int(self.response_headers['Cache-Control'].split('max-age=')[-1].split(',')[0])
                    return max_age > 0
                elif 's-maxage=' in self.response_headers['Cache-Control']:
                    max_age = int(self.response_headers['Cache-Control'].split('s-maxage=')[1].split(',')[0])
                    return max_age > 0
                elif any(t in self.response_headers['Cache-Control'] for t in CACHE_CONTROL_CACHEABLE):
                    return True
            else:
                return False
        except Exception as e:
            logging.warn('Error parsing Cache-Control or Expires header: %s', e)
        return False  # if there was an error, just say not cacheable
    explicitly_cacheable = property(_get_explicitly_cacheable) 

    def _get_implicitly_cacheable(self):
        '''Based on MIME type, do we think this is cacheable?'''
        return self.category in CACHEABLE_CATEGORIES
    implicitly_cacheable = property(_get_implicitly_cacheable)

    def _get_tcp_handshake(self):
        return self.timings['connect'] > 0
    tcp_handshake = property(_get_tcp_handshake)
    
    def _get_ssl_handshake(self):
        return self.timings['ssl'] > 0
    ssl_handshake = property(_get_ssl_handshake)

    def __str__(self):
        return self.url
    def __repr__(self):
        return self.url


class Har(object):
    '''Encapsulates an HTTP Archive (HAR)'''

    def __init__(self, har_json):
        if har_json['log']['pages'] == [] or har_json['log']['entries'] == []:
            raise HarError('HAR is empty: %s' % har_json)

        self.data = har_json
        self.objects = []  # all objects, in order
        self.object_lists = defaultdict(list)
        self._sizes = []  # all object sizes, for computing mean/median
        self._hosts = set()
        self.page_start_time = datetime.datetime.strptime(\
            self.data['log']['pages'][0]['startedDateTime'],\
            '%Y-%m-%dT%H:%M:%S.%fZ')

        self._num_objects = 0
        self._num_bytes = 0
        self._num_explicitly_cacheable_objects = 0
        self._num_implicitly_cacheable_objects = 0
        self._num_explicitly_cacheable_bytes = 0
        self._num_implicitly_cacheable_bytes = 0
        self._num_http_objects = 0
        self._num_https_objects = 0
        self._num_tcp_handshakes = 0
        self._num_ssl_handshakes = 0
        self._total_tcp_handshake_ms = 0
        self._total_ssl_handshake_ms = 0
        self._total_handshake_ms = 0

        for obj_json in self.data['log']['entries']:
            try:
                obj = HarObject(obj_json)
                if not obj.sanity_check(print_report=False): continue
                #print '%d\t%s (%s)\t%s' % (obj.content_size, obj.mime_type, obj.category, obj.domain)

                self.objects.append(obj)
                self.object_lists[obj.category].append(obj)
                self._sizes.append(obj.content_size)
                self._hosts.add(obj.host)

                self._num_objects += 1
                self._num_bytes += obj.content_size

                if obj.protocol == 'http':
                    self._num_http_objects += 1
                elif obj.protocol == 'https':
                    self._num_https_objects += 1

                if obj.explicitly_cacheable:
                    self._num_explicitly_cacheable_objects += 1
                    self._num_explicitly_cacheable_bytes += obj.body_size
                if obj.implicitly_cacheable:
                    self._num_implicitly_cacheable_objects += 1
                    self._num_implicitly_cacheable_bytes += obj.body_size
                if obj.tcp_handshake:
                    self._num_tcp_handshakes += 1
                if obj.ssl_handshake:
                    self._num_ssl_handshakes += 1
                if obj.timings['connect'] >= 0:
                    self._total_tcp_handshake_ms += obj.timings['connect']
                    self._total_handshake_ms += obj.timings['connect']
                if obj.timings['ssl'] >= 0:
                    self._total_ssl_handshake_ms += obj.timings['ssl']
                    self._total_handshake_ms += obj.timings['ssl']
            except Exception as e:
                logging.warn('Error parsing HAR object:%s\n%s', e, obj_json)


    def sanity_check(self):
        for obj in [o for sublist in self.object_lists.values() for o in sublist]:
            obj.sanity_check()

    @classmethod
    def from_file(cls, path):
        with open(path, 'r') as f:
            data = json.load(f)
        f.closed
        return Har(data)

    @classmethod
    def sanitize_url(cls, url):
        return re.sub(r'[/\;,><&*:%=+@!#^()|?^]', '-', url)

    def get_by_name(self, name):
        try:
            return getattr(self, name)
        except:
            logging.warn('No property named "%s"' % name)
            return None

    def _get_url(self):
        id = self.data['log']['pages'][0]['id']
        title = self.data['log']['pages'][0]['title']

        return id if '://' in id else title
    url = property(_get_url)
    
    def _get_base_url(self):
        return self.url.split('://')[-1]
    base_url = property(_get_base_url)

    @property
    def on_load(self):
        return float(self.data['log']['pages'][0]['pageTimings']['onLoad'])

    @property
    def on_content_load(self):
        return float(self.data['log']['pages'][0]['pageTimings']['onContentLoad'])

    def _get_file_types(self):
        return self.object_lists.keys()
    file_types = property(_get_file_types)

    def get_objects(self, obj_type):
        return self.object_lists[obj_type]

    def _get_hosts(self):
        return self._hosts
    hosts = property(_get_hosts)

    def _get_num_hosts(self):
        return len(self._hosts)
    num_hosts = property(_get_num_hosts)

    def get_num_objects_by_type(self, obj_type):
        return len(self.object_lists[obj_type])

    def get_num_bytes_by_type(self, obj_type):
        ''' Returns total size, in bytes, of all objects of the specified type'''
        size = 0
        for obj in self.object_lists[obj_type]:
            size += obj.content_size
        return size

    def _get_num_objects(self):
        return self._num_objects
    num_objects = property(_get_num_objects)

    def _get_num_bytes(self):
        return self._num_bytes
    num_bytes = property(_get_num_bytes)

    def _get_num_mbytes(self):
        return self.num_bytes / 1000000.0
    num_mbytes = property(_get_num_mbytes)

    @property
    def mean_object_size(self):
        return numpy.mean(self._sizes)

    @property
    def median_object_size(self):
        return numpy.median(self._sizes)

    def _get_num_explicitly_cacheable_objects(self):
        return self._num_explicitly_cacheable_objects
    num_explicitly_cacheable_objects = property(_get_num_explicitly_cacheable_objects)

    def _get_num_explicitly_cacheable_bytes(self):
        return self._num_explicitly_cacheable_bytes
    num_explicitly_cacheable_bytes = property(_get_num_explicitly_cacheable_bytes)
    
    def _get_num_implicitly_cacheable_objects(self):
        return self._num_implicitly_cacheable_objects
    num_implicitly_cacheable_objects = property(_get_num_implicitly_cacheable_objects)

    def _get_num_implicitly_cacheable_bytes(self):
        return self._num_implicitly_cacheable_bytes
    num_implicitly_cacheable_bytes = property(_get_num_implicitly_cacheable_bytes)

    def _get_num_http_objects(self):
        return self._num_http_objects
    num_http_objects = property(_get_num_http_objects)

    def _get_num_https_objects(self):
        return self._num_https_objects
    num_https_objects = property(_get_num_https_objects)

    def _get_num_tcp_handshakes(self):
        return self._num_tcp_handshakes
    num_tcp_handshakes = property(_get_num_tcp_handshakes)

    def _get_num_ssl_handshakes(self):
        return self._num_ssl_handshakes
    num_ssl_handshakes = property(_get_num_ssl_handshakes)

    def _get_total_tcp_handshake_ms(self):
        return self._total_tcp_handshake_ms
    total_tcp_handshake_ms = property(_get_total_tcp_handshake_ms)
    
    def _get_total_ssl_handshake_ms(self):
        return self._total_ssl_handshake_ms
    total_ssl_handshake_ms = property(_get_total_ssl_handshake_ms)

    def _get_total_handshake_ms(self):
        return self._total_handshake_ms
    total_handshake_ms = property(_get_total_handshake_ms)

    def _get_profile(self):
        profile = {'num-objects-by-type':{}, 'num-bytes-by-type':{}}
        for t in self.file_types:
            profile['num-objects-by-type'][t] = self.get_num_objects_by_type(t)
            profile['num-bytes-by-type'][t] = self.get_num_bytes_by_type(t)
        profile['num-objects'] = self.num_objects
        profile['num-bytes'] = self.num_bytes
        profile['mean-object-size'] = self.mean_object_size
        profile['median-object-size'] = self.median_object_size
        profile['num-explicitly-cacheable-objects'] = self.num_explicitly_cacheable_objects
        profile['num-explicitly-cacheable-bytes'] = self.num_explicitly_cacheable_bytes
        profile['num-implicitly-cacheable-objects'] = self.num_implicitly_cacheable_objects
        profile['num-implicitly-cacheable-bytes'] = self.num_implicitly_cacheable_bytes
        profile['num-hosts'] = len(self.hosts)
        profile['num-tcp-handshakes'] = self.num_tcp_handshakes
        profile['num-ssl-handshakes'] = self.num_ssl_handshakes
        profile['total-tcp-handshake-ms'] = self.total_tcp_handshake_ms
        profile['total-ssl-handshake-ms'] = self.total_ssl_handshake_ms
        profile['total-handshake-ms'] = self.total_handshake_ms
        profile['percentage-explicitly-cacheable-bytes'] = \
            self.num_explicitly_cacheable_bytes / float(self.num_bytes)\
            if self.num_bytes else 0
        profile['percentage-implicitly-cacheable-bytes'] = \
            self.num_implicitly_cacheable_bytes / float(self.num_bytes)\
            if self.num_bytes else 0
        return profile
    profile = property(_get_profile)

    def __str__(self):
        return '%s (%s)' % (self.data['log']['pages'][0]['title'],\
                            self.data['log']['creator']['name'])
    def __repr__(self):
        return self.__str__()



def main():
    with open(args.har, 'r') as f:
        data = json.load(f)
    f.closed
    
    h = Har(data)

    if args.sanity_check:
        h.sanity_check()

    print h
    print pprint.pformat(h.profile)


if __name__ == '__main__':
    # set up command line args
    parser = argparse.ArgumentParser(description='Analyze a HAR file.')
    parser.add_argument('har', help='HAR file to analyze')
    parser.add_argument('-s', '--sanity_check', action='store_true', default=False, help='Check for problems in the HAR file')
    parser.add_argument('-q', '--quiet', action='store_true', default=False, help='only print errors')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='print debug info. --quiet wins if both are present')
    args = parser.parse_args()

    
    # set up logging
    if args.quiet:
        level = logging.WARNING
    elif args.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(
        format = "%(levelname) -10s %(asctime)s %(module)s:%(lineno) -7s %(message)s",
        level = level
    )

    main()
