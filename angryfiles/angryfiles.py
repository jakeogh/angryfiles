#!/usr/bin/env python

import sys
import os
import pprint
import argparse
import random
import struct
import time
import itertools
import subprocess
from collections import defaultdict

TOTALS_DICT = defaultdict(int)

global VALID_TYPES
VALID_TYPES = ['file', 'dir', 'symlink', 'broken_symlink', 'self_symlink', 'circular_symlink', 'link', 'fifo']

def random_bytes(count):
    assert isinstance(count, int)
    with open('/dev/urandom', "rb") as fd:
        return fd.read(count)

def random_filename_length():
    return random.SystemRandom().randint(0, 255)  # returns max of 255

def get_random_filename():
    length = random_filename_length()
    name = random_bytes(length)  # broken
    return name

def random_utf8():
    gotutf8 = False
    while not gotutf8:
        codepoint = random.SystemRandom().randint(0, 4294967296)
        possible_utf8_bytes = struct.pack(">I", codepoint)
        try:
            possible_utf8_bytes.decode('UTF8')  # todo https://docs.python.org/3/library/codecs.html#error-handlers
            gotutf8 = True
        except UnicodeDecodeError:
            pass
    return possible_utf8_bytes

def write_file(name, data=b''):
    assert isinstance(name, bytes)
    assert isinstance(data, bytes)
    with open(name, 'xb') as fh:
        fh.write(data)

def valid_filename_bytes():
    '''
        everything but 'NULL' (0) and '/' (47)
        interestingly, '/' (47) is a valid symlink dest
        includes '.' (46) but it is not a valid single byte
        filename to create since it always already exists
    '''
    ans = set([bytes([b]) for b in list(itertools.chain(range(1, 47), range(48, 256)))])
    # old_method = set([bytes(chr(x), encoding='Latin-1') for x in range(0, 256)]) - set([b'\x00', b'\x2F'])
    # assert ans == old_method
    assert len(ans) == 254
    return ans

def valid_symlink_dest_bytes():  # todo use
    ans = valid_filename_bytes() | set(b'/')
    assert len(ans) == 255
    return ans

def writable_one_byte_filenames():
    '''
        '.' (46) is not a valid one byte file name but is a valid symlink destination
    '''
    ans = valid_filename_bytes() - {b'.'}
    assert len(ans) == 253  # (256 - [\x00, \x46, \x47])
    return ans

def writable_two_byte_filenames():
    '''
        '..' (46, 46) is not a valid two byte file name but is a valid symlink destination
    '''
    ans = set(itertools.product(valid_filename_bytes(), repeat=2)) - {(b'.', b'.')}
    assert len(ans) == 64515
    return ans

def create_object(name, file_type, target=b'.'):  # fixme: dont imply target
    if file_type not in VALID_TYPES:
        print("you must specify one of:", VALID_TYPES)
        os._exit(1)
    if file_type == 'file':
        write_file(name)
    elif file_type == 'dir':
        os.makedirs(name)
    elif file_type == 'symlink':
        os.symlink(target, name)
    elif file_type == 'broken_symlink':
        # setting target to a random byte does not gurantee a broken symlink
        # in the case of a fixed target like b'a' _at least_ one symlink
        # will be circular and therefore not broken.
        #   (in the complete coverage of n bytes case, when n=1 the 'a' symlink
        #   will be circular if 'a' is the chosen random symlink dest)
        # method:
        #   1. set target ../ OUTSIDE (because one inside could name clash)
        #      the current folder
        #   2. choose a path guranteed to not exist
        # to gurantee the target does not exist:
        #   1. assume the "root" folder tree is deleted every run
        #   2. assume a custom ../$dest_dir_$timestamp/name DOES NOT EXIST

        non_existing_target = b'../' + str(time.time()).encode('UTF8') + b'/' + name
        os.symlink(non_existing_target, name)

    elif file_type == 'self_symlink':
        os.symlink(name, name)
#   elif file_type == 'circular_symlink':
        # todo, below is wrong, what was I thinking with \x00?
        # check the byte (int) value, if it's >0, add 1, if it's = max_value then return \x00,
        # this way every symlink has a unique existing (or soon exising) target.
        # might be a nice way to generate circular symlinks... must skip '.', '..', '/', '\x00'
#       os.symlink(name_back_to_name, name)
    else:
        print("unsupported file_type:", file_type)
        os._exit(1)

def make_all_one_byte_objects(dest_dir, file_type, count, target=b'.'):
    os.makedirs(dest_dir)
    os.chdir(dest_dir)
    for byte in writable_one_byte_filenames():
        create_object(name=byte, file_type=file_type, target=target)
    os.chdir(DEST_DIR)
    check_file_count(dest_dir=dest_dir, count=count, file_type=file_type)

def make_all_one_byte_objects_each_in_byte_number_folder(dest_dir, file_type, count):
    os.makedirs(dest_dir)
    os.chdir(dest_dir)
    for byte in writable_one_byte_filenames():
        byte_folder = str(ord(byte)).zfill(3)
        os.makedirs(byte_folder)
        os.chdir(byte_folder)
        create_object(byte, file_type)
        os.chdir(b'../')
    os.chdir(DEST_DIR)
    check_file_count(dest_dir=dest_dir, count=count, file_type=file_type)

def make_all_two_byte_objects(dest_dir, file_type, count):
    os.makedirs(dest_dir)
    os.chdir(dest_dir)
    for first_byte in valid_filename_bytes():
        for second_byte in valid_filename_bytes():
            file_name = first_byte + second_byte
            if file_name != b'..':  # '..' is not a valid 2 byte file name but is a valid symlink destination
                create_object(file_name, file_type)
    os.chdir(DEST_DIR)
    check_file_count(dest_dir=dest_dir, count=count, file_type=file_type)

def make_all_length_objects(dest_dir, file_type, count, target=b'.'):
    os.makedirs(dest_dir)
    os.chdir(dest_dir)
    byte_length = 1
    while byte_length < 256:
        file_name = b'a' * byte_length
        create_object(file_name, file_type, target=target)
        byte_length += 1
    os.chdir(DEST_DIR)
    check_file_count(dest_dir=dest_dir, count=count, file_type=file_type)

def check_file_count(dest_dir, count, file_type):
    if not os.path.isdir(dest_dir):
        print("dest_dir:", dest_dir, "is not a dir")
        os._exit(1)
    manual_count = len(os.listdir(dest_dir))
    if manual_count != count:
        print("dest_dir:", dest_dir, "has", manual_count, "files. Expected:", count)
        os._exit(1)
    TOTALS_DICT[file_type] += manual_count

class DefaultHelpParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('error: %s\n\n' % message)
        self.print_help()
        sys.exit(2)

    def _get_option_tuples(self, option_string):  # https://bugs.python.org/issue14910
        return []

class SmartFormatter(argparse.HelpFormatter):
    def _split_lines(self, text, width):
        # this is the RawTextHelpFormatter._split_lines
        if text.startswith('R|'):
            return text[2:].splitlines()
        return argparse.HelpFormatter._split_lines(self, text, width)

def main():
    # 1 byte names
    # expected file count = 255 - 2 = 253 (. and / note 0 is NULL)
    # /bin/ls -A 1/1_byte_file_names | wc -l returns 254 because one file is '\n'
    make_all_one_byte_objects(b'files/all_1_byte_file_names', 'file', 253)
    make_all_one_byte_objects_each_in_byte_number_folder(b'files/all_1_byte_file_names_one_per_folder', 'file', 253)
    make_all_one_byte_objects(b'dirs/all_1_byte_dir_names', 'dir', 253)
    make_all_one_byte_objects(b'symlinks/all_1_byte_symlink_names_to_dot', 'symlink', 253)  # can cause code to fail on recursion +/+/+/+ -> .
    make_all_one_byte_objects(b'symlinks/all_1_byte_symlink_names_to_dotdot', 'symlink', 253, b'..')
    make_all_one_byte_objects(b'symlinks/all_1_byte_symlink_names_to_dev_null', 'symlink', 253, b'/dev/null')
    make_all_one_byte_objects(b'symlinks/all_1_byte_broken_symlink_names', 'broken_symlink', 253)
    make_all_one_byte_objects(b'symlinks/all_1_byte_self_symlink_names', 'self_symlink', 253)


    if cmd_args.long_tests:
        # 2 byte names
        # expected file count = (255 - 1) * (255 - 1) = 64516 - 1 = 64515
        # since only NULL and / are invalid, and there is no '..' file
        # /bin/ls -A -f --hide-control-chars 1/2_byte_file_names | wc -l returns 64515
        make_all_two_byte_objects(b'files/all_2_byte_file_names', 'file', 64515)

        make_all_two_byte_objects(b'dirs/all_2_byte_dir_names', 'dir', 64515)  # takes forever to delete
        make_all_two_byte_objects(b'symlinks/all_2_byte_symlink_names_to_dot', 'symlink', 64515)
        make_all_two_byte_objects(b'symlinks/all_2_byte_symlink_names_to_dotdot', 'symlink', 64515, b'..')
        make_all_two_byte_objects(b'symlinks/all_2_byte_symlink_names_to_dev_null', 'symlink', 64515, b'/dev/null')
        make_all_two_byte_objects(b'symlinks/all_2_byte_broken_symlink_names', 'broken_symlink', 64515)

    # all length objects
    # expected file count = 255
    make_all_length_objects(b'files/all_length_file_names', 'file', 255)
    make_all_length_objects(b'symlinks/all_length_symlink_names_to_dot', 'symlink', 255)
    make_all_length_objects(b'symlinks/all_length_symlink_names_to_dotdot', 'symlink', 255, b'..')
    make_all_length_objects(b'symlinks/all_length_symlink_names_to_dev_null', 'symlink', 255, b'/dev/null')
    make_all_length_objects(b'symlinks/all_length_broken_symlink_names', 'broken_symlink', 255)
    make_all_length_objects(b'symlinks/all_length_self_symlink_names', 'self_symlink', 255)
    make_all_length_objects(b'dirs/all_length_dir_names', 'dir', 255)

    # max length objects


if __name__ == '__main__':
    parser = DefaultHelpParser(formatter_class=SmartFormatter, add_help=True)
    long_tests_help = 'R|Run tests that may take hours to complete and even longer to delete.\n'
    dest_dir_help = 'R|Directory to make files under. Should be empty.\n'
    parser.add_argument("dest_dir", help=dest_dir_help, type=str)
    parser.add_argument("--long-tests", help=long_tests_help, action="store_true", default=False)
    cmd_args = parser.parse_args()
    DEST_DIR = os.path.abspath(os.path.expanduser(cmd_args.dest_dir))
    os.makedirs(DEST_DIR)
    os.chdir(DEST_DIR)
    main()

    TOTALS_DICT['all_symlinks'] = TOTALS_DICT['symlink'] + \
                                  TOTALS_DICT['broken_symlink'] + \
                                  TOTALS_DICT['self_symlink'] + \
                                  TOTALS_DICT['circular_symlink']
    pprint.pprint(TOTALS_DICT)
    command = ' '.join(['/usr/bin/find', DEST_DIR, '|', 'wc -l'])
    final_count = int(subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True))
    #print("final_count:", final_count)
    if cmd_args.long_tests:
        assert final_count == 69113
    else:
        assert final_count == 4089
