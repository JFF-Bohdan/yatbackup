#!/usr/bin/env python3
from optparse import OptionParser
import os
import configparser
import subprocess
import datetime
import hashlib
import codecs
import glob
import time
from system.utils.stopwatch import Stopwatch
from system.log_support import init_logger
from system.shared import makeAbsoluteAppPath, mkdir_p, LastErrorHolder, scanBoolean

class YatBackup(LastErrorHolder):
    """
    Yet another tiny backup
    """
    def __init__(self, logger, configFile):
        LastErrorHolder.__init__(self)

        self.logger = logger
        self.configFileName = configFile
        self.config = None

        self.targetDirectory = None
        self.destinationDirectory = None
        self.compressingAlgo = None

        self.destinationFileName = None

        self.produceOutputHashFile = False
        self.outputHashFileAlgo = None

        self.similarArchiveFileName = None
        self.similarArchiveHash = None

        self.startDtsUtc = datetime.datetime.utcnow()


    def setError(self, errorText):
        self.logger.error(errorText)
        return LastErrorHolder.setError(self, errorText)

    def __combineIgnoreItems(self, algo):
        ret = []

        exclude = ""
        if self.config.has_option("main", "exclude"):
            exclude = self.config["main"]["exclude"]

        exludeRecursive = ""
        if self.config.has_option("main", "exclude_recursive"):
            exludeRecursive = self.config["main"]["exclude_recursive"]

        excludePrefix = ""
        if self.config.has_option("main", "exclude_prefix"):
            excludePrefix = self.config["main"]["exclude_prefix"]

        exclude = [item for item in str(exclude).split(",") if len(item) > 0]
        exludeRecursive = [item for item in str(exludeRecursive).split(",") if len(item) > 0]

        if algo == "7z":
            for item in exclude:
                if len(excludePrefix) > 0:
                    item = excludePrefix + item
                ret.append("-x!{}".format(item))

            for item in exludeRecursive:
                if len(excludePrefix) > 0:
                    item = excludePrefix + item
                ret.append("-xr!{}".format(item))

        elif algo == "bz2":
            for item in exclude:
                ret.append("--exclude={}".format(item))

            for item in exludeRecursive:
                ret.append("--exclude={}".format(item))

        return ret

    def __loadingConfig(self):
        self.config = configparser.ConfigParser()
        self.config.read(self.configFileName)

        self.targetDirectory = self.config["main"]["target"]
        self.destinationDirectory = self.config["main"]["destination"]
        self.compressingAlgo = self.config["main"]["compressor"]

        self.targetDirectory = os.path.normpath(makeAbsoluteAppPath(self.targetDirectory))
        self.destinationDirectory = os.path.normpath(makeAbsoluteAppPath(self.destinationDirectory))

        self.logger.info("target directory: {}".format(self.targetDirectory))
        self.logger.info("destination directory: {}".format(self.destinationDirectory))

        if (not os.path.exists(self.targetDirectory)) or (not os.path.isdir(self.targetDirectory)):
            return self.setError("target directory does not exists or is not directory\ndirectory: {}".format(self.targetDirectory))

        if not os.path.exists(self.destinationDirectory):
            if not mkdir_p(self.destinationDirectory):
                return self.setError("can't create destination directory")

        if not os.path.isdir(self.destinationDirectory):
            return self.setError("destination directory is't directory")

        self.produceOutputHashFile = False
        if self.config.has_option("main", "add_hash_file"):
            self.produceOutputHashFile = scanBoolean(self.config["main"]["add_hash_file"])

        self.outputHashFileAlgo = "md5"
        if self.config.has_option("main", "hash_algo_for_file"):
            self.outputHashFileAlgo = self.config["main"]["hash_algo_for_file"]

        return True

    def __substCompressor(self, algo):
        lookup = algo
        if lookup == "bz2":
            lookup = "tar"

        if self.config.has_option("compressors", lookup):
            return self.config["compressors"][lookup]

        return lookup

    def __getExtenstionForCompressor(self, algo):
        """
        Returns result archive file extension
        :param algo: compression algorithm
        :return: result file extension
        """
        if algo == "bz2":
            return "tar.bz2"

        return algo

    @staticmethod
    def __calculateFileHash(fileName, hashAlgo):
        """
        Calculates file hash digest

        :param fileName: file name
        :param hashAlgo: hash algorithm (md5, sha256, etc.)
        :return: hex digest
        """
        block_size = 1024*4
        hasher = hashlib.new(hashAlgo)
        with open(fileName, 'rb') as f:
            for block in iter(lambda: f.read(block_size), b''):
                hasher.update(block)

        return hasher.hexdigest()

    def __produceOutputHashFile(self):
        """
        Produces output hash file for archive
        :return: None
        """
        hashDigest = self.__calculateFileHash(self.destinationFileName, self.outputHashFileAlgo)
        baseName = os.path.splitext(self.destinationFileName)[0]

        outputFileName = baseName + "." + self.outputHashFileAlgo
        print("outputFileName = {}".format(outputFileName))

        output = "{} *{}".format(hashDigest, os.path.basename(self.destinationFileName))
        with codecs.open(outputFileName, "w", "utf-8") as f:
            f.write(output)

    def __getLastArchiveInDestinationDirectory(self):
        """
        Returns last similar archive file name (by file modification DTS)
        :return: file name of last archive or None if no archive files available
        """

        #loading archives list (with same extension)
        mask = os.path.join(self.destinationDirectory, "*.{}".format(self.__getExtenstionForCompressor(self.compressingAlgo)))
        data = glob.glob(mask)
        filesList = []
        for item in data:
            if not os.path.exists(item):
                continue

            if not os.path.isfile(item):
                continue

            if item == self.destinationFileName:
                continue

            filesList.append(item)

        if len(filesList) == 0:
            return None

        #loading last modification DTS for each file
        ret = []
        for file in filesList:
            ct = time.ctime(os.path.getmtime(file))

            item = (file, ct)
            ret.append(item)

        #sorting in reverse order
        ret = sorted(ret, key=lambda k: k[1], reverse=True)

        return ret[0][0]

    def __getTargetFileName(self):
        now = datetime.datetime.now()

        ret = os.path.basename(self.targetDirectory)
        ret = "{}-{}.{}".format(
            ret,
            now.strftime("%Y%m%dT%H%M%S"),
            self.__getExtenstionForCompressor(self.compressingAlgo)
        )
        ret = os.path.join(self.destinationDirectory, ret)
        ret = os.path.normpath(ret)

        return ret

    def __compressDirectory(self):
        args = []

        compressorExecutable = self.__substCompressor(self.compressingAlgo)

        # calculating destination file name
        self.destinationFileName = self.__getTargetFileName()

        excludeItems = self.__combineIgnoreItems(self.compressingAlgo)

        if self.compressingAlgo == "7z":
            args = [
                compressorExecutable,
                "a"
            ]

            args.append(self.destinationFileName)
            args.append(self.targetDirectory)
            args.extend(excludeItems)
        elif self.compressingAlgo == "bz2":
            args = [
                compressorExecutable,
                "-cvjSf",
                self.destinationFileName,
                self.targetDirectory
            ]

            args.extend(excludeItems)

        self.logger.debug("args = {}".format(args))
        self.logger.info("compressing started")
        subprocess.call(args)
        self.logger.info("compressing finished")
#
        return True

    def __canStoreResultArchive(self):
        """
        Checks that we can store current archive file
        :return:
        """
        similarArchive = self.__getLastArchiveInDestinationDirectory()
        similarFileHash = None
        if similarArchive is None:
            return True

        similarFileHash = self.__calculateFileHash(similarArchive, "sha256")
        destinationFileHash = self.__calculateFileHash(self.destinationFileName, "sha256")

        ret = (similarFileHash != destinationFileHash)
        if not ret:
            self.similarArchiveFileName = similarArchive
            self.similarArchiveHash = destinationFileHash

        return ret

    def __markSkipRun(self):
        """
        Creates .skip file with log information
        :return: None
        """

        #creating new skip file
        baseName = os.path.splitext(self.destinationFileName)[0]
        skipNotificationFileName = baseName + ".skip"

        with codecs.open(skipNotificationFileName, "w", "utf-8") as f:
            f.write("== yatbackup result skipped ==\n")
            f.write("\tstart DTS (UTC)             : {}\n".format(self.startDtsUtc))
            f.write("\tsimilar archive file name   : {}\n".format(self.similarArchiveFileName))
            f.write("\tfile name (will be removed) : {}\n".format(self.destinationFileName))
            f.write("\tdestination hash            : {}\n".format(self.similarArchiveHash))
            f.write("\tcurrent DTS (UTC)           : {}\n".format(datetime.datetime.utcnow()))

        # looking for old .skip files and removing them
        mask = os.path.join(self.destinationDirectory, "*.skip")
        data = glob.glob(mask)

        for item in data:
            if not os.path.exists(item):
                continue

            if not os.path.isfile(item):
                continue

            if item == skipNotificationFileName:
                continue

            os.remove(item)

    def process(self):

        self.logger.debug("reading config file")
        if not self.__loadingConfig():
            return False

        if not self.__compressDirectory():
            return False

        assert self.destinationFileName is not None
        assert os.path.exists(self.destinationFileName)

        if not self.__canStoreResultArchive():
            self.logger.info("similar archive found. Adding skip file")
            self.__markSkipRun()

            self.logger.info("removing new archive")
            os.remove(self.destinationFileName)
            return True

        if self.produceOutputHashFile:
            self.logger.info("producing output hash file")
            self.__produceOutputHashFile()

        return True

def main():
    stopwatch = Stopwatch(True, True)

    logger = init_logger()

    parser = OptionParser()
    parser.add_option("-c", "--config", type="string", dest="config_file", default=None, help="path to configuration files")

    (commandLineOptions, args) = parser.parse_args()

    if commandLineOptions.config_file is None:
        logger.error("no config file specified...")
        return -1

    configFile = commandLineOptions.config_file
    configFile = os.path.normpath(configFile)

    if (not os.path.exists(configFile)) or (not os.path.isfile(configFile)):
        logger.error("config file does not exists or is not folder: {}".format(configFile))
        return -2

    processor = YatBackup(logger, configFile)
    if not processor.process():
        logger.error("ERR: {}".format(processor.errorText))
        return -3

    logger.info(str(stopwatch))
    return 0

if __name__ == '__main__':
    ret = main()
    exit(ret)

