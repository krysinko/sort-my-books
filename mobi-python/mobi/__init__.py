#!/usr/bin/env python
# encoding: utf-8
"""
Mobi.py

Created by Elliot Kroo on 2009-12-25.
Copyright (c) 2009 Elliot Kroo. All rights reserved.
"""

import sys
import os
import unittest
from urllib.error import URLError

import isbnlib
from struct import *
from pprint import pprint
from . import utils
from .lz77 import uncompress_lz77

from urllib import request
import xml.etree.ElementTree as ET
from urllib.error import URLError


class Mobi:
    def parse(self):
        """ reads in the file, then parses record tables"""
        self.contents = self.f.read();
        self.header = self.parseHeader();
        self.records = self.parseRecordInfoList();
        self.readRecord0()

    def readRecord(self, recordnum, disable_compression=False):
        if self.config:
            if self.config['palmdoc']['Compression'] == 1 or disable_compression:
                return self.contents[
                       self.records[recordnum]['record Data Offset']:self.records[recordnum + 1]['record Data Offset']];
            elif self.config['palmdoc']['Compression'] == 2:
                result = uncompress_lz77(self.contents[
                                         self.records[recordnum]['record Data Offset']:self.records[recordnum + 1][
                                                                                           'record Data Offset'] -
                                                                                       self.config['mobi'][
                                                                                           'extra bytes']])
                return result

    def readImageRecord(self, imgnum):
        if self.config:
            recordnum = self.config['mobi']['First Image index'] + imgnum;
            return self.readRecord(recordnum, disable_compression=True);

    def author(self):
        "Returns the author of the book"
        return self.config['exth']['records'][100]

    def title(self):
        "Returns the title of the book"
        return self.config['mobi']['Full Name']

    def isbn(self):
        return self.config['exth']['recods'].get(104, None)

    ###########  Private API ###########################

    def __init__(self, filename):
        self.newFileName = ''
        self.authorName = ''
        try:
            if isinstance(filename, str):
                self.f = open(filename, "rb");
            else:
                self.f = filename;
        except IOError as e:
            sys.stderr.write("Could not open %s! " % filename);
            raise e;
        self.offset = 0;

    def __iter__(self):
        if not self.config: return;
        for record in range(1, self.config['mobi']['First Non-book index'] - 1):
            yield self.readRecord(record);

    def parseRecordInfoList(self):
        records = {};
        # read in all records in info list
        for recordID in range(self.header['number of records']):
            headerfmt = '>II'
            headerlen = calcsize(headerfmt)
            fields = [
                "record Data Offset",
                "UniqueID",
            ]
            # create tuple with info
            results = list(zip(fields, unpack(headerfmt, self.contents[self.offset:self.offset + headerlen])))

            # increment offset into file
            self.offset += headerlen

            # convert tuple to dictionary
            resultsDict = utils.toDict(results);

            # futz around with the unique ID record, as the uniqueID's top 8 bytes are
            # really the "record attributes":
            resultsDict['record Attributes'] = (resultsDict['UniqueID'] & 0xFF000000) >> 24;
            resultsDict['UniqueID'] = resultsDict['UniqueID'] & 0x00FFFFFF;

            # store into the records dict
            records[resultsDict['UniqueID']] = resultsDict;

        return records;

    def parseHeader(self):
        headerfmt = '>32shhIIIIII4s4sIIH'
        headerlen = calcsize(headerfmt)
        fields = [
            "name",
            "attributes",
            "version",
            "created",
            "modified",
            "backup",
            "modnum",
            "appInfoId",
            "sortInfoID",
            "type",
            "creator",
            "uniqueIDseed",
            "nextRecordListID",
            "number of records"
        ]

        # unpack header, zip up into list of tuples
        results = list(zip(fields, unpack(headerfmt, self.contents[self.offset:self.offset + headerlen])))

        # increment offset into file
        self.offset += headerlen

        # convert tuple array to dictionary
        resultsDict = utils.toDict(results);

        return resultsDict

    # https://e-isbn.pl/IsbnWeb/start/export_search.xml?dummy=1&szukaj_prefiks=9788381911917
    def readRecord0(self):
        palmdocHeader = self.parsePalmDOCHeader();
        MobiHeader = self.parseMobiHeader();
        exthHeader = None
        if MobiHeader['Has EXTH Header']:
            exthHeader = self.parseEXTHHeader();
            meta = {}
            isbn = ''
            if exthHeader['records'] and exthHeader['records'].get(104, None) is not None:
                try:
                    isbn = isbnlib.ean13(
                        exthHeader['records'].get(104).decode('unicode_escape').encode('latin1').decode('utf8').replace(
                            '-', ''))
                    meta = isbnlib.meta(isbn)
                    # print(meta, isbn)
                except TypeError:
                    print('error for ', exthHeader['records'].get(104).decode('unicode_escape').encode('latin1').decode(
                        'utf8').replace('-', ''))
            elif exthHeader['records'] and exthHeader['records'].get(100, None) is not None and exthHeader[
                'records'].get(503, None) is not None:
                self.newFileName = (exthHeader['records'].get(100)).decode('unicode_escape').encode('latin1').decode(
                    'utf8') + ' - ' + (exthHeader['records'].get(503)).decode('unicode_escape').encode('latin1').decode(
                    'utf8')
                self.authorName = (exthHeader['records'].get(100)).decode('unicode_escape').encode('latin1').decode(
                    'utf8')

                try:
                    isbn = isbnlib.isbn_from_words(self.newFileName)
                    if isbn:
                        meta = isbnlib.meta(isbnlib.ean13(isbn))
                except TypeError:
                    print('error for ', self.newFileName)
                print(meta, isbn)

            if meta == {} and isbn != '':

                try:
                    url = "https://e-isbn.pl/IsbnWeb/start/export_search.xml?dummy=1&szukaj_prefiks=" + isbn
                    print("Retrieving", url)
                    html = request.urlopen(url)
                    data = html.read()

                    data = data.replace(
                        b' release="3.0"\n    xmlns:schemaLocation="http://ns.editeur.org/onix/3.0/reference https://e-isbn.pl/IsbnWeb/schemas/ONIX_BookProduct_3.0_reference.xsd"\n    xmlns="http://ns.editeur.org/onix/3.0/reference" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
                        b'').replace(b'\n', b'')
                    tree = ET.XML(data)

                    titleNode = tree.find('./Product/DescriptiveDetail/TitleDetail/TitleElement/TitleText')
                    authorNode = tree.find('./Product/DescriptiveDetail/Contributor/PersonNameInverted')
                    title = titleNode.text if titleNode is not None else ''
                    author = authorNode.text.replace(',', '') if authorNode is not None else ''
                    print(author, title)
                    self.newFileName = author + ' - ' + title
                except URLError:
                    pass

        self.config = {
            'palmdoc': palmdocHeader,
            'mobi': MobiHeader,
            'exth': exthHeader
        }

    def parseEXTHHeader(self):
        headerfmt = '>III'
        headerlen = calcsize(headerfmt)

        fields = [
            'identifier',
            'header length',
            'record Count'
        ]

        # unpack header, zip up into list of tuples
        results = list(zip(fields, unpack(headerfmt, self.contents[self.offset:self.offset + headerlen])))

        # convert tuple array to dictionary
        resultsDict = utils.toDict(results);

        self.offset += headerlen;
        resultsDict['records'] = {};
        for record in range(resultsDict['record Count']):
            recordType, recordLen = unpack(">II", self.contents[self.offset:self.offset + 8]);
            recordData = self.contents[self.offset + 8:self.offset + recordLen];
            resultsDict['records'][recordType] = recordData;
            self.offset += recordLen;

        return resultsDict;

    def parseMobiHeader(self):
        headerfmt = '> IIII II 40s III IIIII IIII I 36s IIII 8s HHIIIII'
        headerlen = calcsize(headerfmt)

        fields = [
            "identifier",
            "header length",
            "Mobi type",
            "text Encoding",

            "Unique-ID",
            "Generator version",

            "-Reserved",

            "First Non-book index",
            "Full Name Offset",
            "Full Name Length",

            "Language",
            "Input Language",
            "Output Language",
            "Format version",
            "First Image index",

            "First Huff Record",
            "Huff Record Count",
            "First DATP Record",
            "DATP Record Count",

            "EXTH flags",

            "-36 unknown bytes, if Mobi is long enough",

            "DRM Offset",
            "DRM Count",
            "DRM Size",
            "DRM Flags",

            "-Usually Zeros, unknown 8 bytes",

            "-Unknown",
            "Last Image Record",
            "-Unknown",
            "FCIS record",
            "-Unknown",
            "FLIS record",
            "Unknown"
        ]

        # unpack header, zip up into list of tuples
        results = list(zip(fields, unpack(headerfmt, self.contents[self.offset:self.offset + headerlen])))

        # convert tuple array to dictionary
        resultsDict = utils.toDict(results);

        resultsDict['Start Offset'] = self.offset;

        resultsDict['Full Name'] = (self.contents[
                                    self.records[0]['record Data Offset'] + resultsDict['Full Name Offset']:
                                    self.records[0]['record Data Offset'] + resultsDict['Full Name Offset'] +
                                    resultsDict['Full Name Length']])

        resultsDict['Has DRM'] = resultsDict['DRM Offset'] != 0xFFFFFFFF;

        resultsDict['Has EXTH Header'] = (resultsDict['EXTH flags'] & 0x40) != 0;

        self.offset += resultsDict['header length'];

        def onebits(x, width=16):
            return len([x for x in (str((x >> i) & 1) for i in range(width - 1, -1, -1)) if x == "1"]);

        resultsDict['extra bytes'] = 2 * onebits(unpack(">H", self.contents[self.offset - 2:self.offset])[0] & 0xFFFE)

        return resultsDict;

    def parsePalmDOCHeader(self):
        headerfmt = '>HHIHHHH'
        headerlen = calcsize(headerfmt)
        fields = [
            "Compression",
            "Unused",
            "text length",
            "record count",
            "record size",
            "Encryption Type",
            "Unknown"
        ]
        offset = self.records[0]['record Data Offset'];
        # create tuple with info
        results = list(zip(fields, unpack(headerfmt, self.contents[offset:offset + headerlen])))

        # convert tuple array to dictionary
        resultsDict = utils.toDict(results);

        self.offset = offset + headerlen;
        return resultsDict


class MobiTests(unittest.TestCase):
    def setUp(self):
        self.mobitest = Mobi("../test/CharlesDarwin.mobi");

    def testParse(self):
        self.mobitest.parse();
        pprint(self.mobitest.config)

    def testRead(self):
        self.mobitest.parse();
        content = ""
        for i in range(1, 5):
            content += self.mobitest.readRecord(i);

    def testImage(self):
        self.mobitest.parse();
        pprint(self.mobitest.records);
        for record in range(4):
            f = open("imagerecord%d.jpg" % record, 'w')
            f.write(self.mobitest.readImageRecord(record));
            f.close();

    def testAuthorTitle(self):
        self.mobitest.parse()
        self.assertEqual(self.mobitest.author(), 'Charles Darwin')
        self.assertEqual(self.mobitest.title(), 'The Origin of Species by means ' +
                         'of Natural Selection, 6th Edition')


if __name__ == '__main__':
    unittest.main()
