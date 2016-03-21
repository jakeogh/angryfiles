
# angryfiles

**angryfiles** attempts to create a filesystem heirachary which is as diverse as possible.

Inspired by https://github.com/petrosagg/wtfiles

```
usage: angryfiles [-h] [--long-tests] dest_dir

positional arguments:
  dest_dir      Directory to make files under. Should be empty.

optional arguments:
  -h, --help    show this help message and exit
  --long-tests  Run tests that may take hours to complete and even longer to delete.
```
 
**example:**
 
```  
$ ./angryfiles ./test
  
$ ls -al ./test
total 1324
drwxr-xr-x  13 user user    4096 Mar 21 03:46 .
drwxr-xr-x   3 user user    4096 Mar 21 03:46 ..
drwxr-xr-x   2 user user    4096 Mar 21 03:46 1_byte_broken_symlink_names
drwxr-xr-x 255 user user    4096 Mar 21 03:46 1_byte_dir_names
drwxr-xr-x   2 user user    4096 Mar 21 03:46 1_byte_file_names
drwxr-xr-x   2 user user    4096 Mar 21 03:46 1_byte_self_symlink_names
drwxr-xr-x   2 user user    4096 Mar 21 03:46 1_byte_symlink_names
drwxr-xr-x   2 user user 1064960 Mar 21 03:46 2_byte_file_names
drwxr-xr-x   2 user user   49152 Mar 21 03:46 all_length_broken_symlink_names
drwxr-xr-x 257 user user   49152 Mar 21 03:46 all_length_dir_names
drwxr-xr-x   2 user user   49152 Mar 21 03:46 all_length_file_names
drwxr-xr-x   2 user user   49152 Mar 21 03:46 all_length_self_symlink_names
drwxr-xr-x   2 user user   49152 Mar 21 03:46 all_length_symlink_names
``` 

**Realted Software**
https://github.com/omaciel/fauxfactory


