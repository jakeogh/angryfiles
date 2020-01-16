#!/usr/bin/env python

import sys
import click
import os
import pprint
from shutil import copy
#import argparse
import random
import struct
import time
import itertools
import subprocess
from pathlib import Path
from collections import defaultdict

global TOTALS_DICT
TOTALS_DICT = defaultdict(int)

def make_working_dir(path):
    os.makedirs(path)
    TOTALS_DICT['working_dir'] += 1

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

#  TODO evaluate /usr/lib64/python3.4/site-packages/bs4/dammit.py
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

def write_file(name, data=b'', template_file=None):
    assert isinstance(name, bytes)
    assert isinstance(data, bytes)
    if template_file:
        assert data == b''
        name = Path(os.fsdecode(name))
        copy(template_file, name, follow_symlinks=False)
    else:
        with open(name, 'xb') as fh:
            fh.write(name)

def valid_filename_bytes():
    '''
        valid bytes to include in a filename

        everything but 'NULL' (0) and '/' (47)
        Notes:
            '/' (47) is a valid symlink dest                        bytes([47]) == b'/' == b'\x2F'
            '.' (46) is not a valid single byte filename to create  bytes([46]) == b'.' == b'\x2E'
                since it always already exists
    '''
    ans = set([bytes([b]) for b in list(itertools.chain(range(1, 47), range(48, 256)))])
    # old_method = set([bytes(chr(x), encoding='Latin-1') for x in range(0, 256)]) - set([b'\x00', b'\x2F'])
    another_method = set([bytes([x]) for x in range(0, 256) if x not in (0, 0x2f)])      # python@altendky
    # assert ans == old_method
    assert ans == another_method
    assert len(ans) == 254
    assert b'\x00' not in ans  # NULL
    assert b'\x2F' not in ans  # /
    assert b'/' not in ans     # /
    for byte in ans:
        assert isinstance(byte, bytes)
    return ans

def valid_symlink_dest_bytes():  # todo use
    ans = valid_filename_bytes() | set(b'/')
    assert len(ans) == 255
    assert b'\x2F' in ans  # /
    assert b'/' in ans     # /
    return ans

def writable_one_byte_filenames():
    '''
        '.' (46) is not a valid one byte file name but is a valid symlink destination
    '''
    ans = valid_filename_bytes() - {b'.'}
    assert len(ans) == 253  # 256 - [\x00, \x46, \x47]
                            # 256 - [NULL, '.', '/']
    return ans

def writable_two_byte_filenames():
    '''
        '..' (46, 46) is not a valid two byte file name but is a valid symlink destination
    '''
    ans = set(itertools.product(valid_filename_bytes(), repeat=2)) - {(b'.', b'.')}
    assert len(ans) == 64515
    assert b'\x46\x46' not in ans   # '..'
    assert b'..' not in ans         # '..'
    return ans

def create_object(name, file_type, target=b'.', content=b'', template_file=None):  # fixme: dont imply target
    valid_types = ['file', 'dir', 'symlink', 'broken_symlink', 'self_symlink',
                   'next_symlink', 'next_symlinkable_byte', 'circular_symlink',
                   'link', 'fifo']

    assert file_type in valid_types
    if template_file:
        assert file_type == 'file'
        assert not content

    if file_type == 'file':
        write_file(name=name, data=content, template_file=template_file)
    elif file_type == 'dir':
        os.makedirs(name)
    elif file_type == 'symlink':
        os.symlink(target, name)
    elif file_type == 'broken_symlink':
        # setting target to a random byte does not gurantee a broken symlink
        # in the case of a fixed target like b'a' _at least_ one symlink
        # will be circular and therefore not broken
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
        # assert non_existing_target does not exist
        os.symlink(non_existing_target, name)
    elif file_type == 'self_symlink':
        os.symlink(name, name)
    elif file_type == 'next_symlinkable_byte':
        # symlink to the next valid symlink target byte
        # next means:
        #   if the symlink name is a single byte:
        #       increment the symlink name byte to the next valid symlink target
        #       if there is no "next" valid symlink target (when symlink name
        #       b'\x377' (255) is reached), return the "first" valid symlink
        #       target b'\x001' (001).
        #
        # Note: b'.', b'..' and b'/' are valid symlink targets
        # assert next_symlinkable_byte is not b'\x00'
        # os.symlink(next_symlinkable_byte, name)
        pass
    elif file_type == 'next_symlink':
        # symlink to the next valid symlink _name_ byte
        # "next" means:
        #   if the symlink name is a single byte:
        #       increment the symlink name byte to the next valid symlink name
        #       if there is no "next" valid symlink name (when symlink name
        #       b'\x377' (255) is reached), return the "first" valid symlink
        #       name b'\x001' (001).
        #
        # assert next_symlink is not b'..'
        # assert next_symlink is not b'.'
        # assert next_symlink is not b'/'
        # assert next_symlink is not b'\x00'
        # os.symlink(next_symlink, name)
        pass

def make_all_one_byte_objects(angry_dir, dest_dir, file_type, count, target=b'.', self_content=False):
    make_working_dir(dest_dir)
    os.chdir(dest_dir)
    for byte in writable_one_byte_filenames():
        if self_content:
            create_object(name=byte, file_type=file_type, target=target, content=byte)
        else:
            create_object(name=byte, file_type=file_type, target=target)
    os.chdir(angry_dir)
    check_file_count(dest_dir=dest_dir, count=count, file_type=file_type)

def make_all_one_byte_objects_each_in_byte_number_folder(angry_dir, dest_dir, file_type, count):
    make_working_dir(dest_dir)
    os.chdir(dest_dir)
    for byte in writable_one_byte_filenames():
        byte_folder = str(ord(byte)).zfill(3)
        make_working_dir(byte_folder)
        os.chdir(byte_folder)
        create_object(byte, file_type)
        os.chdir(b'../')
    os.chdir(angry_dir)
    check_file_count(dest_dir=dest_dir, count=count, file_type=file_type)

def make_all_two_byte_objects(angry_dir, dest_dir, file_type, count, target=b'.'):
    make_working_dir(dest_dir)
    os.chdir(dest_dir)
    for first_byte in valid_filename_bytes():
        for second_byte in valid_filename_bytes():
            file_name = first_byte + second_byte
            if file_name != b'..':  # '..' is not a valid 2 byte file name but is a valid symlink destination
                create_object(file_name, file_type, target=target)
    os.chdir(angry_dir)
    check_file_count(dest_dir=dest_dir, count=count, file_type=file_type)

def make_one_all_byte_file(angry_dir, dest_dir, template_file=None):
    make_working_dir(dest_dir)
    os.chdir(dest_dir)
    file_name = b''
    for next_byte in valid_filename_bytes():
        file_name += next_byte
    print(repr(file_name))
    create_object(file_name, file_type='file', template_file=template_file)
    os.chdir(angry_dir)
    check_file_count(dest_dir=dest_dir, count=1, file_type='file')

def make_all_length_objects(angry_dir, dest_dir, file_type, count, target=b'.', self_content=False, all_bytes=False):
    make_working_dir(dest_dir)
    os.chdir(dest_dir)
    byte_length = 1
    all_valid_bytes = list(valid_filename_bytes())
    assert all_valid_bytes
    all_valid_bytes.sort(reverse=True)
    file_name = None
    while byte_length < 256:
        if all_bytes:
            try:
                next_byte = all_valid_bytes.pop()
            except IndexError:
                next_byte = b'\x01'
            if file_name is None:
                file_name = next_byte
            else:
                file_name = file_name + next_byte
        else:
            file_name = b'a' * byte_length
        if self_content:
            create_object(file_name, file_type, target=target, content=file_name)
        else:
            create_object(file_name, file_type, target=target)
        byte_length += 1
    os.chdir(angry_dir)
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


def main(angry_dir, long_tests):
    # 1 byte names
    # expected file count = 255 - 2 = 253 (. and / note 0 is NULL)
    # /bin/ls -A 1/1_byte_file_names | wc -l returns 254 because one file is '\n'
    make_all_one_byte_objects(angry_dir, b'files/all_1_byte_file_names', 'file', 253)
    make_all_one_byte_objects(angry_dir, b'files/all_1_byte_file_names_self_content', 'file', 253, self_content=True)
    make_all_one_byte_objects_each_in_byte_number_folder(angry_dir, b'files/all_1_byte_file_names_one_per_folder', 'file', 253)
    make_all_one_byte_objects(angry_dir, b'dirs/all_1_byte_dir_names', 'dir', 253)
    make_all_one_byte_objects(angry_dir, b'symlinks/all_1_byte_symlink_names_to_dot', 'symlink', 253)  # can cause code to fail on recursion +/+/+/+ -> .
    make_all_one_byte_objects(angry_dir, b'symlinks/all_1_byte_symlink_names_to_dotdot', 'symlink', 253, b'..')
    make_all_one_byte_objects(angry_dir, b'symlinks/all_1_byte_symlink_names_to_dev_null', 'symlink', 253, b'/dev/null')
    make_all_one_byte_objects(angry_dir, b'symlinks/all_1_byte_broken_symlink_names', 'broken_symlink', 253)
    make_all_one_byte_objects(angry_dir, b'symlinks/all_1_byte_self_symlink_names', 'self_symlink', 253)

    # all length objects
    # expected file count = 255
    make_all_length_objects(angry_dir, b'files/all_length_file_names', 'file', 255)
    make_all_length_objects(angry_dir, b'files/all_length_file_names_self_content', 'file', 255, self_content=True)
    make_all_length_objects(angry_dir, b'files/all_length_file_names_all_bytes__self_content', 'file', 255, self_content=True, all_bytes=True)
    make_all_length_objects(angry_dir, b'symlinks/all_length_symlink_names_to_dot', 'symlink', 255)
    make_all_length_objects(angry_dir, b'symlinks/all_length_symlink_names_to_dotdot', 'symlink', 255, b'..')
    make_all_length_objects(angry_dir, b'symlinks/all_length_symlink_names_to_dev_null', 'symlink', 255, b'/dev/null')
    make_all_length_objects(angry_dir, b'symlinks/all_length_broken_symlink_names', 'broken_symlink', 255)
    make_all_length_objects(angry_dir, b'symlinks/all_length_self_symlink_names', 'self_symlink', 255)
    make_all_length_objects(angry_dir, b'dirs/all_length_dir_names', 'dir', 255)

    if long_tests:
        # 2 byte names
        # expected file count = (255 - 1) * (255 - 1) = 64516 - 1 = 64515
        # since only NULL and / are invalid, and there is no '..' file
        # /bin/ls -A -f --hide-control-chars 1/2_byte_file_names | wc -l returns 64515
        make_all_two_byte_objects(angry_dir, b'files/all_2_byte_file_names', 'file', 64515)

        make_all_two_byte_objects(angry_dir, b'dirs/all_2_byte_dir_names', 'dir', 64515)  # takes forever to delete
        make_all_two_byte_objects(angry_dir, b'symlinks/all_2_byte_symlink_names_to_dot', 'symlink', 64515)
        make_all_two_byte_objects(angry_dir, b'symlinks/all_2_byte_symlink_names_to_dotdot', 'symlink', 64515, b'..')
        make_all_two_byte_objects(angry_dir, b'symlinks/all_2_byte_symlink_names_to_dev_null', 'symlink', 64515, b'/dev/null')
        make_all_two_byte_objects(angry_dir, b'symlinks/all_2_byte_broken_symlink_names', 'broken_symlink', 64515)

    # TODO max length objects

def one_mad_file(angry_dir, template_file):
    make_one_all_byte_file(angry_dir=angry_dir,
                           dest_dir=b'one_mad_file',
                           template_file=template_file)

@click.command()
@click.argument('path', type=click.Path(exists=False, path_type=str, allow_dash=True), nargs=1)
@click.option('--long-tests', is_flag=True)
@click.option('--one-angry-file', is_flag=True)
@click.option('--template-file', type=click.Path(exists=True, dir_okay=False, file_okay=True, path_type=str, allow_dash=True))
def cli(path, long_tests, one_angry_file, template_file):
    angry_dir = Path(path).expanduser().absolute()  #hmmm. ~ is a valid path name Bug.
    if angry_dir.exists():
        raise ValueError("path: {} already exists".format(angry_dir))

    angry_dir.mkdir()
    os.chdir(angry_dir)
    if one_angry_file:
        one_mad_file(angry_dir=angry_dir, template_file=template_file)
    else:
        assert not template_file
        main(angry_dir=angry_dir, long_tests=long_tests)

    TOTALS_DICT['all_symlinks'] = TOTALS_DICT['symlink'] + \
                                  TOTALS_DICT['broken_symlink'] + \
                                  TOTALS_DICT['self_symlink'] + \
                                  TOTALS_DICT['circular_symlink']
    pprint.pprint(TOTALS_DICT)
    command = ' '.join(['/usr/bin/find', angry_dir.as_posix(), "-printf '\n' |", 'wc -l'])
    final_count = int(subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True))
    print("final_count:", final_count)
    expected_final_count = TOTALS_DICT['all_symlinks'] + \
                           TOTALS_DICT['file'] + \
                           TOTALS_DICT['dir'] + \
                           TOTALS_DICT['working_dir'] + 4  # top level dirs: angry_dir/dirs
                                                           #                          /files
                                                           #                          /symlinks
    if long_tests:
        print("expected_final_count:", expected_final_count)
        assert final_count == expected_final_count
    else:
        print("expected_final_count:", expected_final_count)
        assert final_count == expected_final_count

if __name__ == '__main__':
    cli()

