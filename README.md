# yatbackup
Yet Another Tiny Backup.

![Backup](./img/backup.png)

## General information

Backup tool for one of my production instances. It implements very simple logic for my special requirements.

Algorithm: `yatbackup` can compress whole folder using specified archiver. In case, when another backup with same hash available in destination folder, new archive will be deleted.

Yes, it's all.

Why do I need it? I need create backup of some folder using `cron`, but I don't need duplicate archives.

Also, I need to understand that utility successfully finished, even no new archives was created.

## How to use it

First of all, you need to create configuration file which describes your requirements. Then you can call `yatbackup` using this command line:

```Bash
yatbackup.py --config /etc/yatbackup/conf.conf
```

In this case we running `yatbackup` with configuration in file `/etc/yatbackup/conf.conf`

## Configuration files

### General information
`yatbackup` behaviour can be controlled using configuration files. Examples can be found in `/examples` folder of repository.

### `main` section
All configuration files must contain `main` section

```ini
[main]
target=s:/AmSystem/tapvisor
destination=s:/dest
exclude=tmp,sendfile_download,dev,log,nmon,.git,.idea,uploads
exclude_recursive=__pycache__
exclude_prefix=tapvisor/
compressor=7z
add_hash_file=True
hash_algo_for_file=sha256
```

In this case, we want to backup `s:/AmSystem/tapvisor` folder into `s:/dest` folder using `7z` archiver. Also, we want ignore folder/file with name `__pycache__` in all directories (recursivelly). In root folder we want ignore all these folders:

* tmp
* sendfile_download
* dev
* log
* nmon
* .git
* .idea
* uploads


Also, we want calculate hash of result file using sha-256 and save it in same folder.


### `compressors` section
Configuration files can have section with pathes of all known archivers.

Example:

```ini
[compressors]
7z=c:/Program Files/7-Zip/7z.exe
tar=c:/Program Files (x86)/Git/bin/tar.exe
bzip2=c:/Program Files (x86)/Git/bin/bzip2.exe
```

When path specified this path will be used when archiver specified in `[main]compressor`


## Output example

For example, in case when we have configuration as listed below, when we call `yatbackup` calling:

`> d:\Python35\python.exe yatbackup.py --config .\examples\tapvisor.conf`

We will get files `tapvisor-20170411T183716.7z` and `tapvisor-20170411T183716.sha256` in `s:\dest\` folder. 

Next, we call our command again and will get `tapvisor-20170411T183742.skip` which demostrates that `yatbackup` successfully executed and no backups created. 

Next, we will call our command again and again receiving new `.skip` file without new archives created. Old `.skip` files will be automatically deleted. So, using `.skip` files we can understand that yatbackup was called and successfully finished all operations, but no new archive was created.

New archive will be created only if target folder content will be cnahged.


## Usage example

In my case I preffer use `yatbackup` via `cron`. To edit system cron file you shall call:
`$ sudo crontab -e`

And add something like this:
`0 3 * * * /home/bohdan/yatbackup/yatbackup.py --config /home/bohdan/yatbackupconfig/tapvisor.conf&`

In this case every night at 3 AM `yatbackup` will be executed using config in `/home/bohdan/yatbackupconfig/tapvisor.conf`

If you want to play with `cron` rules you can use this [Online Cron Rules Editor](https://crontab.guru/)

Enjoy!
