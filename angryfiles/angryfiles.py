#!/usr/bin/env python

# flake8: noqa
# pylint: disable=missing-docstring               # [C0111] docstrings are always outdated and wrong
# pylint: disable=fixme                           # [W0511] todo is encouraged
# pylint: disable=line-too-long                   # [C0301]
# pylint: disable=too-many-instance-attributes    # [R0902]
# pylint: disable=too-many-lines                  # [C0302] too many lines in module
# pylint: disable=invalid-name                    # [C0103] single letter var names, name too descriptive
# pylint: disable=too-many-return-statements      # [R0911]
# pylint: disable=too-many-branches               # [R0912]
# pylint: disable=too-many-statements             # [R0915]
# pylint: disable=too-many-arguments              # [R0913]
# pylint: disable=too-many-nested-blocks          # [R1702]
# pylint: disable=too-many-locals                 # [R0914]
# pylint: disable=too-few-public-methods          # [R0903]
# pylint: disable=no-member                       # [E1101] no member for base
# pylint: disable=attribute-defined-outside-init  # [W0201]
# pylint: disable=too-many-boolean-expressions    # [R0916] in if statement
from __future__ import annotations

import itertools
import os
import pprint
import random
import struct
import subprocess
import sys
import time
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from shutil import copy
from tempfile import TemporaryDirectory
from typing import ByteString
from typing import Generator
from typing import Iterable
from typing import Set

import click
from asserttool import ic
from clicktool import click_add_options
from clicktool import click_global_options
from clicktool import tv
from eprint import eprint
from getdents import paths
from mptool import output
from with_chdir import chdir

global TOTALS_DICT
TOTALS_DICT = defaultdict(int)


def make_working_dir(path: bytes) -> None:
    assert isinstance(path, bytes)
    os.makedirs(path)
    # path.mkdir(parents=True)
    new_dir_count = (
        len(Path(os.fsdecode(path)).parts) - 1
    )  # bug if other tests use same subfolder
    TOTALS_DICT["working_dir"] += max(1, new_dir_count)


def random_bytes(count: int) -> bytes:
    assert isinstance(count, int)
    with open("/dev/urandom", "rb") as fd:
        return fd.read(count)


def random_filename_length() -> int:
    return random.SystemRandom().randint(0, 255)  # returns max of 255


def get_random_filename() -> bytes:
    length = random_filename_length()
    name = random_bytes(length)  # broken
    return name


# evaluate /usr/lib64/python3.4/site-packages/bs4/dammit.py
def random_utf8() -> bytes:
    gotutf8 = False
    while not gotutf8:
        codepoint = random.SystemRandom().randint(0, 4294967296)
        possible_utf8_bytes = struct.pack(">I", codepoint)
        try:
            possible_utf8_bytes.decode(
                "UTF8"
            )  # todo https://docs.python.org/3/library/codecs.html#error-handlers
            gotutf8 = True
        except UnicodeDecodeError:
            pass
    return possible_utf8_bytes


# inception bug here...?
def write_file(
    *,
    name: bytes,
    data: bytes,
    template_file: None | bytes = None,
):
    assert isinstance(name, bytes)
    assert isinstance(data, bytes)
    if template_file:
        assert data == b""
        _name = Path(os.fsdecode(name))
        _template_file = Path(os.fsdecode(template_file))
        del name  # todo check exact file was written, needs to be a gateway for all file creation
        copy(_template_file, _name, follow_symlinks=False)
    else:
        with open(name, "xb") as fh:
            fh.write(data)


# prob should be Set[bytes]
def valid_filename_bytes() -> Set[list[bytes]]:
    """
    valid bytes to include in a filename

    everything but 'NULL' (0) and '/' (47)
    Notes:
        '/' (47) is a valid symlink dest                        bytes([47]) == b'/' == b'\x2F'
        '.' (46) is not a valid single byte filename to create  bytes([46]) == b'.' == b'\x2E'
            since it always already exists
    """
    # old_method = set([bytes(chr(x), encoding='Latin-1') for x in range(0, 256)]) - set([b'\x00', b'\x2F'])
    ans = set([bytes([b]) for b in list(itertools.chain(range(1, 47), range(48, 256)))])
    # ans = {[bytes([b]) for b in list(itertools.chain(range(1, 47), range(48, 256)))]}  # TypeError: unhashable type: 'list'
    another_method = set(
        [bytes([x]) for x in range(0, 256) if x not in (0, 0x2F)]
    )  # python@altendky
    # assert ans == old_method
    assert ans == another_method
    assert len(ans) == 254
    assert b"\x00" not in ans  # NULL
    assert b"\x2F" not in ans  # /
    assert b"/" not in ans  # /
    for byte in ans:
        assert isinstance(byte, bytes)
    return ans


def valid_symlink_dest_bytes() -> set[bytes]:  # todo use
    # ans = valid_filename_bytes() | set(b'/')
    ans = valid_filename_bytes() | {b"/"}
    assert len(ans) == 255
    assert b"\x2F" in ans  # /
    assert b"/" in ans  # /
    return ans


def writable_one_byte_filenames():
    """
    '.' (46) is not a valid one byte file name but is a valid symlink destination
    """
    ans = valid_filename_bytes() - {b"."}
    assert len(ans) == 253  # 256 - [\x00, \x46, \x47]
    # 256 - [NULL, '.', '/']
    return ans


def writable_two_byte_filenames():
    """
    '..' (46, 46) is not a valid two byte file name but is a valid symlink destination
    """
    ans = set(itertools.product(valid_filename_bytes(), repeat=2)) - {(b".", b".")}
    assert len(ans) == 64515
    assert b"\x46\x46" not in ans  # '..'
    assert b".." not in ans  # '..'
    return ans


def create_object(
    *,
    name: bytes,
    file_type: str,
    content: None | bytes,
    target: None | bytes,
    template_file: None | bytes = None,
    verbose: bool | int | float,
) -> None:  # fixme: dont imply target

    valid_types = [
        "file",
        "dir",
        "symlink",
        "broken_symlink",
        "self_symlink",
        "next_symlink",
        "next_symlinkable_byte",
        "circular_symlink",
        "link",
        "fifo",
    ]

    # assert content is None

    # if verbose:
    #    ic(name, file_type, content, target, template_file,)

    assert file_type in valid_types
    if template_file:
        assert file_type == "file"
        assert not content

    if file_type == "file":
        if content is None:
            content = b""
        write_file(name=name, data=content, template_file=template_file)
        return

    if file_type == "dir":
        os.makedirs(name)
        return

    if file_type == "symlink":
        assert target
        os.symlink(target, name)
        return

    if file_type == "broken_symlink":
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
        non_existing_target = b"../" + str(time.time()).encode("UTF8") + b"/" + name
        # assert non_existing_target does not exist
        os.symlink(non_existing_target, name)
        return

    if file_type == "self_symlink":
        os.symlink(name, name)
        return

    if file_type == "next_symlinkable_byte":
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

    if file_type == "next_symlink":
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

    return


def make_all_one_byte_objects(
    *,
    root_dir: bytes,
    dest_dir: bytes,
    file_type: str,
    count: int,
    target: None | bytes,
    self_content: bool,
    verbose: bool | int | float,
    prepend: None | bytes = None,
):
    make_working_dir(dest_dir)

    with chdir(dest_dir, verbose=verbose):
        for byte in writable_one_byte_filenames():
            if prepend:
                byte = prepend + byte
            if self_content:
                create_object(
                    name=byte,
                    file_type=file_type,
                    target=target,
                    content=byte,
                    verbose=verbose,
                )
            else:
                create_object(
                    name=byte,
                    file_type=file_type,
                    target=target,
                    content=None,
                    verbose=verbose,
                )

    with chdir(root_dir, verbose=verbose):
        check_file_count(
            dest_dir=dest_dir,
            count=count,
            file_type=file_type,
            verbose=verbose,
        )


def make_all_one_byte_objects_each_in_byte_number_folder(
    *,
    root_dir: bytes,
    dest_dir: bytes,
    file_type: str,
    count: int,
    self_content: bool,
    verbose: bool | int | float,
    prepend: None | bytes = None,
) -> None:
    make_working_dir(dest_dir)
    os.chdir(dest_dir)
    for byte in writable_one_byte_filenames():
        byte_folder = str(ord(byte)).zfill(3)
        make_working_dir(byte_folder.encode("utf8"))
        os.chdir(byte_folder)
        content = None
        if self_content:
            content = byte
        if prepend:
            byte = prepend + byte
        create_object(
            name=byte,
            file_type=file_type,
            content=content,
            target=b".",
            verbose=verbose,
        )
        os.chdir(b"../")
    os.chdir(root_dir)
    check_file_count(
        dest_dir=dest_dir,
        count=count,
        file_type=file_type,
        verbose=verbose,
    )


def make_all_two_byte_objects(
    *,
    root_dir: bytes,
    dest_dir: bytes,
    file_type: str,
    count: int,
    target: bytes,
    verbose: bool | int | float,
) -> None:
    make_working_dir(dest_dir)
    os.chdir(dest_dir)
    for first_byte in valid_filename_bytes():
        for second_byte in valid_filename_bytes():
            file_name = first_byte + second_byte
            if (
                file_name != b".."
            ):  # '..' is not a valid 2 byte file name but is a valid symlink destination
                create_object(
                    name=file_name,
                    file_type=file_type,
                    target=target,
                    content=None,
                    verbose=verbose,
                )
    os.chdir(root_dir)
    check_file_count(
        dest_dir=dest_dir,
        count=count,
        file_type=file_type,
        verbose=verbose,
    )


def make_one_all_byte_file(
    *,
    root_dir: bytes,
    dest_dir: bytes,
    template_file: None | bytes,
    verbose: bool | int | float,
) -> None:
    make_working_dir(dest_dir)
    os.chdir(dest_dir)
    file_name = b""
    for next_byte in valid_filename_bytes():
        file_name += next_byte
    # print(repr(file_name))
    create_object(
        name=file_name,
        file_type="file",
        template_file=template_file,
        content=None,
        target=b".",
        verbose=verbose,
    )
    os.chdir(root_dir)
    check_file_count(
        dest_dir=dest_dir,
        count=1,
        file_type="file",
        verbose=verbose,
    )


def make_all_length_objects(
    *,
    root_dir: bytes,
    dest_dir: bytes,
    file_type: str,
    count: int,
    self_content: bool,
    target: None | bytes,
    all_bytes: bool,
    verbose: bool | int | float,
) -> None:
    make_working_dir(dest_dir)
    with chdir(
        dest_dir,
        verbose=verbose,
    ):
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
                    next_byte = b"\x01"
                if file_name is None:
                    file_name = next_byte
                else:
                    file_name = file_name + next_byte
            else:
                file_name = b"a" * byte_length
            if self_content:
                create_object(
                    name=file_name,
                    file_type=file_type,
                    target=target,
                    content=file_name,
                    verbose=verbose,
                )
            else:
                create_object(
                    name=file_name,
                    file_type=file_type,
                    target=target,
                    content=None,
                    verbose=verbose,
                )
            byte_length += 1

    with chdir(
        root_dir,
        verbose=verbose,
    ):
        check_file_count(
            dest_dir=dest_dir,
            count=count,
            file_type=file_type,
            verbose=verbose,
        )


def check_file_count(
    dest_dir: bytes,
    count: int,
    file_type: str,
    verbose: bool | int | float,
):
    if not os.path.isdir(dest_dir):
        print("dest_dir:", dest_dir, "is not a dir")
        os._exit(1)
    manual_count = len(os.listdir(dest_dir))
    if manual_count != count:
        print("dest_dir:", dest_dir, "has", manual_count, "files. Expected:", count)
        os._exit(1)
    TOTALS_DICT[file_type] += manual_count


def main(
    root_dir,
    long_tests: bool,
    verbose: bool | int | float,
):
    # 1 byte names
    # expected file count = 255 - 2 = 253 (. and / note 0 is NULL)
    # /bin/ls -A 1/1_byte_file_names | wc -l returns 254 because one file is '\n'
    make_all_one_byte_objects(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"files/all_1_byte_file_names",
        file_type="file",
        count=253,
        self_content=False,
        target=None,
    )
    make_all_one_byte_objects(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"files/all_1_byte_file_names_with_a_~_folder/~",
        file_type="file",
        count=253,
        self_content=False,
        target=None,
    )  # 254 not 253 because of the ~ parent dir, but cant set here
    make_all_one_byte_objects(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"files/all_1_byte_file_names_prepended_with_~",
        file_type="file",
        count=253,
        self_content=False,
        target=None,
        prepend=b"~",
    )
    make_all_one_byte_objects(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"files/all_1_byte_file_names_self_content",
        file_type="file",
        count=253,
        self_content=True,
        target=None,
    )
    make_all_one_byte_objects_each_in_byte_number_folder(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"files/all_1_byte_file_names_one_per_folder",
        file_type="file",
        count=253,
        self_content=False,
    )
    make_all_one_byte_objects_each_in_byte_number_folder(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"files/all_1_byte_file_names_one_per_folder_prepended_with_~",
        file_type="file",
        count=253,
        self_content=False,
        prepend=b"~",
    )
    make_all_one_byte_objects_each_in_byte_number_folder(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"dirs/all_1_byte_dir_names_one_per_folder",
        file_type="dir",
        count=253,
        self_content=False,
    )  # not counting the parent int folders?
    make_all_one_byte_objects(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"dirs/all_1_byte_dir_names",
        file_type="dir",
        count=253,
        self_content=False,
        target=None,
    )
    make_all_one_byte_objects(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"symlinks/all_1_byte_symlink_names_to_dot",
        file_type="symlink",
        count=253,
        self_content=False,
        target=b".",
    )  # can cause code to fail on recursion +/+/+/+ -> .
    make_all_one_byte_objects(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"symlinks/all_1_byte_symlink_names_to_dotdot",
        file_type="symlink",
        count=253,
        self_content=False,
        target=b"..",
    )
    make_all_one_byte_objects(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"symlinks/all_1_byte_symlink_names_to_dev_null",
        file_type="symlink",
        count=253,
        self_content=False,
        target=b"/dev/null",
    )
    make_all_one_byte_objects(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"symlinks/all_1_byte_broken_symlink_names",
        file_type="broken_symlink",
        count=253,
        self_content=False,
        target=b".",
    )
    make_all_one_byte_objects(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"symlinks/all_1_byte_self_symlink_names",
        file_type="self_symlink",
        count=253,
        self_content=False,
        target=b".",
    )

    # all length objects
    # expected file count = 255
    make_all_length_objects(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"files/all_length_file_names",
        file_type="file",
        count=255,
        self_content=False,
        target=None,
        all_bytes=False,
    )
    make_all_length_objects(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"files/all_length_file_names_self_content",
        file_type="file",
        count=255,
        self_content=True,
        target=None,
        all_bytes=False,
    )
    make_all_length_objects(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"files/all_length_file_names_all_bytes__self_content",
        file_type="file",
        count=255,
        self_content=True,
        all_bytes=True,
        target=b".",
    )
    make_all_length_objects(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"symlinks/all_length_symlink_names_to_dot",
        file_type="symlink",
        count=255,
        self_content=False,
        target=b".",
        all_bytes=False,
    )
    make_all_length_objects(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"symlinks/all_length_symlink_names_to_dotdot",
        file_type="symlink",
        count=255,
        target=b"..",
        self_content=False,
        all_bytes=False,
    )
    make_all_length_objects(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"symlinks/all_length_symlink_names_to_dev_null",
        file_type="symlink",
        count=255,
        target=b"/dev/null",
        self_content=False,
        all_bytes=False,
    )
    make_all_length_objects(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"symlinks/all_length_broken_symlink_names",
        file_type="broken_symlink",
        count=255,
        self_content=False,
        target=b".",
        all_bytes=False,
    )
    make_all_length_objects(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"symlinks/all_length_self_symlink_names",
        file_type="self_symlink",
        count=255,
        self_content=False,
        target=b".",
        all_bytes=False,
    )
    make_all_length_objects(
        verbose=verbose,
        root_dir=root_dir,
        dest_dir=b"dirs/all_length_dir_names",
        file_type="dir",
        count=255,
        self_content=False,
        target=None,
        all_bytes=False,
    )

    if long_tests:
        # 2 byte names
        # expected file count = (255 - 1) * (255 - 1) = 64516 - 1 = 64515
        # since only NULL and / are invalid, and there is no '..' file
        # /bin/ls -A -f --hide-control-chars 1/2_byte_file_names | wc -l returns 64515
        make_all_two_byte_objects(
            verbose=verbose,
            root_dir=root_dir,
            dest_dir=b"files/all_2_byte_file_names",
            file_type="file",
            count=64515,
            target=None,
        )
        make_all_two_byte_objects(
            verbose=verbose,
            root_dir=root_dir,
            dest_dir=b"dirs/all_2_byte_dir_names",
            file_type="dir",
            count=64515,
            target=None,
        )  # takes forever to delete
        make_all_two_byte_objects(
            verbose=verbose,
            root_dir=root_dir,
            dest_dir=b"symlinks/all_2_byte_symlink_names_to_dot",
            file_type="symlink",
            count=64515,
            target=b".",
        )
        make_all_two_byte_objects(
            verbose=verbose,
            root_dir=root_dir,
            dest_dir=b"symlinks/all_2_byte_symlink_names_to_dotdot",
            file_type="symlink",
            count=64515,
            target=b"..",
        )
        make_all_two_byte_objects(
            verbose=verbose,
            root_dir=root_dir,
            dest_dir=b"symlinks/all_2_byte_symlink_names_to_dev_null",
            file_type="symlink",
            count=64515,
            target=b"/dev/null",
        )
        make_all_two_byte_objects(
            verbose=verbose,
            root_dir=root_dir,
            dest_dir=b"symlinks/all_2_byte_broken_symlink_names",
            file_type="broken_symlink",
            count=64515,
            target=b".",
        )

    # TODO max length objects


def one_mad_file(root_dir, template_file, verbose):
    make_one_all_byte_file(
        root_dir=root_dir,
        dest_dir=b"one_mad_file",
        template_file=template_file,
        verbose=verbose,
    )


@click.command()
@click.argument(
    "output_dir", type=click.Path(exists=False, path_type=str, allow_dash=True), nargs=1
)
@click.option("--stdout", is_flag=True)
@click.option("--long-tests", is_flag=True)
@click.option("--one-angry-file", is_flag=True)
@click.option(
    "--template-file",
    type=click.Path(
        exists=True, dir_okay=False, file_okay=True, path_type=str, allow_dash=True
    ),
)
@click_add_options(click_global_options)
@click.pass_context
def cli(
    ctx,
    *,
    output_dir: str,
    stdout: bool,
    long_tests: bool,
    one_angry_file: bool,
    template_file: str,
    verbose: bool | int | float,
    verbose_inf: bool,
    dict_output: bool,
):

    tty, verbose = tv(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
    )

    if not output_dir:
        assert stdout
        root_dir = Path(
            TemporaryDirectory(
                prefix="tmp-angryfiles-",
                dir="/tmp",
            ).name
        )
    else:
        # ic(output_dir)
        root_dir = (
            Path(output_dir).expanduser().absolute()
        )  # hmmm. ~ is a valid path name Bug.

    if root_dir.exists():
        raise ValueError("output_dir: {} already exists".format(root_dir))
    root_dir.mkdir()

    os.chdir(root_dir)
    if one_angry_file:
        one_mad_file(root_dir=root_dir, template_file=template_file, verbose=verbose)
    else:
        assert not template_file
        main(root_dir=root_dir, long_tests=long_tests, verbose=verbose)

    TOTALS_DICT["all_symlinks"] = (
        TOTALS_DICT["symlink"]
        + TOTALS_DICT["broken_symlink"]
        + TOTALS_DICT["self_symlink"]
        + TOTALS_DICT["circular_symlink"]
    )
    command = " ".join(
        ["/usr/bin/find", root_dir.as_posix(), "-printf '\n' |", "wc -l"]
    )
    final_count = int(
        subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True)
    )

    if one_angry_file:
        top_level = 1  # root_dir
    else:
        top_level = 4  # top level dirs: root_dir/dirs
        #                          /files
        #                          /symlinks

    expected_final_count = (
        TOTALS_DICT["all_symlinks"]
        + TOTALS_DICT["file"]
        + TOTALS_DICT["dir"]
        + TOTALS_DICT["working_dir"]
        + top_level
    )

    # symlink verification
    # broken_symlink + circular_symlink + self_symlink + symlink == all_symlinks
    # note 'symlink' should be named 'unbroken_symlinks_to_another_location'
    assert (
        TOTALS_DICT["broken_symlink"]
        + TOTALS_DICT["circular_symlink"]
        + TOTALS_DICT["self_symlink"]
        + TOTALS_DICT["symlink"]
    ) == TOTALS_DICT["all_symlinks"]

    # if long_tests:
    #    print("expected_final_count:", expected_final_count)
    #    assert final_count == expected_final_count
    # else:
    if not stdout:
        pprint.pprint(TOTALS_DICT)
        print("final_count:", final_count)
        print("expected_final_count:", expected_final_count)
    assert final_count == expected_final_count

    if stdout:
        for path in paths(
            root_dir,
            verbose=verbose,
        ):
            output(
                path.path,
                reason=path,
                tty=tty,
                dict_output=dict_output,
                verbose=verbose,
            )
