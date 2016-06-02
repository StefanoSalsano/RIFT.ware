
# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#

import collections
import json
import os
import re
import shutil
import tarfile
import tempfile
import threading
import uuid
import xml.etree.ElementTree as ET

import tornado
import tornado.escape
import tornado.ioloop
import tornado.web
import tornado.httputil
import requests

# disable unsigned certificate warning
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

import gi
gi.require_version('RwLaunchpadYang', '1.0')
gi.require_version('RwYang', '1.0')
gi.require_version('RwcalYang', '1.0')

from gi.repository import (
        RwcalYang as rwcal,
        NsdYang,
        VnfdYang,
        )
import rift.mano.cloud

from . import archive
from . import checksums
from . import convert
from . import message
from .message import (
        ExportFailure,
        ExportStart,
        ExportSuccess,
        MessageException,
        OnboardDescriptorError,
        OnboardDescriptorFormatError,
        OnboardDescriptorOnboard,
        OnboardDescriptorTimeout,
        OnboardDescriptorValidation,
        OnboardError,
        OnboardFailure,
        OnboardImageUpload,
        OnboardInvalidPath,
        OnboardMissingAccount,
        OnboardMissingContentBoundary,
        OnboardMissingContentType,
        OnboardMissingTerminalBoundary,
        OnboardPackageUpload,
        OnboardPackageValidation,
        OnboardStart,
        OnboardSuccess,
        OnboardUnreadableHeaders,
        OnboardUnreadablePackage,
        OnboardUnsupportedMediaType,
        UpdateChecksumMismatch,
        UpdateDescriptorError,
        UpdateDescriptorFormatError,
        UpdateDescriptorTimeout,
        UpdateDescriptorUpdated,
        UpdateError,
        UpdateFailure,
        UpdateMissingAccount,
        UpdateMissingContentBoundary,
        UpdateMissingContentType,
        UpdateNewDescriptor,
        UpdatePackageUpload,
        UpdateStart,
        UpdateSuccess,
        UpdateUnreadableHeaders,
        UpdateUnreadablePackage,
        UpdateUnsupportedMediaType,
        )
from .tosca import ToscaPackage


class UnreadableHeadersError(MessageException):
    pass


class UnreadablePackageError(MessageException):
    pass


class MissingTerminalBoundary(MessageException):
    pass


class HttpMessageError(Exception):
    def __init__(self, code, msg):
        self.code = code
        self.msg = msg


class RequestHandler(tornado.web.RequestHandler):
    def options(self, *args, **kargs):
        pass

    def set_default_headers(self):
        self.set_header('Access-Control-Allow-Origin', '*')
        self.set_header('Access-Control-Allow-Headers', 'Content-Type, Cache-Control, Accept, X-Requested-With, Authorization')
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, PUT, DELETE')


def boundary_search(fd, boundary):
    """
    Use the Boyer-Moore-Horpool algorithm to find matches to a message boundary
    in a file-like object.

    Arguments:
        fd       - a file-like object to search
        boundary - a string defining a message boundary

    Returns:
        An array of indices corresponding to matches in the file

    """
    # It is easier to work with a search pattern that is reversed with this
    # algorithm
    needle = ''.join(reversed(boundary)).encode()

    # Create a lookup to efficiently determine how far we can skip through the
    # file based upon the characters in the pattern.
    lookup = dict()
    for i, c in enumerate(needle[1:], start=1):
        if c not in lookup:
            lookup[c] = i

    blength = len(boundary)
    indices = list()

    # A buffer that same length as the pattern is used to read characters from
    # the file. Note that characters are added from the left to make for a
    # straight forward comparison with the reversed orientation of the needle.
    buffer = collections.deque(maxlen=blength)
    buffer.extendleft(fd.read(blength))

    # Iterate through the file and construct an array of the indices where
    # matches to the boundary occur.
    index = 0
    while True:
        tail = buffer[0]

        # If the "tail" of the buffer matches the first character in the
        # needle, perform a character by character check.
        if tail == needle[0]:
            for x, y in zip(buffer, needle):
                if x != y:
                    break

            else:
                # Success! Record the index of the of beginning of the match
                indices.append(index)

        # Determine how far to skip based upon the "tail" character
        skip = lookup.get(tail, blength)
        chunk = fd.read(skip)

        if chunk == b'':
            break

        # Push the chunk into the buffer and update the index
        buffer.extendleft(chunk)
        index += skip

    return indices


def extract_package(log, fd, boundary, pkgfile):
    """Extract tarball from multipart message on disk

    Arguments:
        fd       - A file object that the package can be read from
        boundary - a string defining the boundary of different parts in the
                    multipart message.

    """
    log.debug("extracting archive from data")

    # The boundary parameter in the message is defined as the boundary
    # parameter in the message headers prepended by two dashes, i.e.
    # "--{boundary}".
    boundary = "--" + boundary

    # Find the indices of the message boundaries
    boundaries = boundary_search(fd, boundary)
    if not boundaries:
        raise UnreadablePackageError()

    # check that the message has a terminal boundary
    fd.seek(boundaries[-1])
    terminal = fd.read(len(boundary) + 2)
    if terminal != boundary.encode() + b'--':
        raise MissingTerminalBoundary()

    log.debug("search for part containing archive")
    # find the part of the message that contains the descriptor
    for alpha, bravo in zip(boundaries[:-1], boundaries[1:]):
        # Move to the beginning of the message part (and trim the
        # boundary)
        fd.seek(alpha)
        fd.readline()

        # Extract the headers from the beginning of the message
        headers = tornado.httputil.HTTPHeaders()
        while fd.tell() < bravo:
            line = fd.readline()
            if not line.strip():
                break

            headers.parse_line(line.decode('utf-8'))

        else:
            raise UnreadableHeadersError()

        # extract the content disposition and options or move on to the next
        # part of the message.
        try:
            content_disposition = headers['content-disposition']
            disposition, options = tornado.httputil._parse_header(content_disposition)
        except KeyError:
            continue

        # If this is not form-data, it is not what we are looking for
        if disposition != 'form-data':
            continue

        # If there is no descriptor in the options, this data does not
        # represent a descriptor archive.
        if options.get('name', '') != 'descriptor':
            continue

        file_uploaded = options.get('filename', '')

        # Write the archive section to disk
        with open(pkgfile + ".partial", 'wb') as tp:
            log.debug("writing archive ({}) to filesystem".format(pkgfile))

            remaining = bravo - fd.tell()
            while remaining > 0:
                length = min(remaining, 1024)
                tp.write(fd.read(length))
                remaining -= length

            tp.flush()

        # If the data contains a end-of-feed and carriage-return
        # characters, this can cause gzip to issue warning or errors. Here,
        # we check the last to bytes of the data and remove them if they
        # corresponding to '\r\n'.
        with open(pkgfile + ".partial", "rb+") as tp:
            tp.seek(-2, 2)
            if tp.read(2) == b"\r\n":
                tp.seek(-2, 2)
                tp.truncate()

            log.debug("finished writing archive")

        # Strip the "upload" suffix from the basename
        shutil.move(pkgfile + ".partial", pkgfile)

        return file_uploaded

    raise UnreadablePackageError()


@tornado.web.stream_request_body
class StreamingUploadHandler(RequestHandler):
    def initialize(self, log, loop):
        """Initialize the handler

        Arguments:
            log  - the logger that this handler should use
            loop - the tasklets ioloop

        """
        self.transaction_id = str(uuid.uuid4())

        self.loop = loop
        self.log = self.application.get_logger(self.transaction_id)

        self.package_name = None
        self.package_fp = None
        self.boundary = None

        self.log.debug('created handler (transaction_id = {})'.format(self.transaction_id))

    def msg_missing_account(self):
        raise NotImplementedError()

    def msg_missing_content_type(self):
        raise NotImplementedError()

    def msg_unsupported_media_type(self):
        raise NotImplementedError()

    def msg_missing_content_boundary(self):
        raise NotImplementedError()

    def msg_start(self):
        raise NotImplementedError()

    def msg_success(self):
        raise NotImplementedError()

    def msg_failure(self):
        raise NotImplementedError()

    def msg_package_upload(self):
        raise NotImplementedError()

    @tornado.gen.coroutine
    def prepare(self):
        """Prepare the handler for a request

        The prepare function is the first part of a request transaction. It
        creates a temporary file that uploaded data can be written to.

        """
        if self.request.method != "POST":
            return

        self.log.message(self.msg_start())

        try:
            # Retrieve the content type and parameters from the request
            content_type = self.request.headers.get('content-type', None)
            if content_type is None:
                raise HttpMessageError(400, self.msg_missing_content_type())

            content_type, params = tornado.httputil._parse_header(content_type)

            if "multipart/form-data" != content_type.lower():
                raise HttpMessageError(415, self.msg_unsupported_media_type())

            if "boundary" not in params:
                raise HttpMessageError(400, self.msg_missing_content_boundary())

            self.boundary = params["boundary"]
            self.package_fp = tempfile.NamedTemporaryFile(
                    prefix="pkg-",
                    delete=False,
                    )

            self.package_name = self.package_fp.name

            self.log.debug('writing to {}'.format(self.package_name))

        except HttpMessageError as e:
            self.log.message(e.msg)
            self.log.message(self.msg_failure())

            raise tornado.web.HTTPError(e.code, e.msg.name)

        except Exception as e:
            self.log.exception(e)
            self.log.message(self.msg_failure())

    @tornado.gen.coroutine
    def data_received(self, data):
        """Write data to the current file

        Arguments:
            data - a chunk of data to write to file

        """
        self.package_fp.write(data)

    def post(self):
        """Handle a post request

        The function is called after any data associated with the body of the
        request has been received.

        """
        self.package_fp.close()
        self.log.message(self.msg_package_upload())


class UploadHandler(StreamingUploadHandler):
    """
    This handler is used to upload archives that contain VNFDs, NSDs, and PNFDs
    to the launchpad. This is a streaming handler that writes uploaded archives
    to disk without loading them all into memory.
    """

    def msg_missing_account(self):
        return OnboardMissingAccount()

    def msg_missing_content_type(self):
        return OnboardMissingContentType()

    def msg_unsupported_media_type(self):
        return OnboardUnsupportedMediaType()

    def msg_missing_content_boundary(self):
        return OnboardMissingContentBoundary()

    def msg_start(self):
        return OnboardStart()

    def msg_success(self):
        return OnboardSuccess()

    def msg_failure(self):
        return OnboardFailure()

    def msg_package_upload(self):
        return OnboardPackageUpload()

    def post(self):
        """Handle a post request

        The function is called after any data associated with the body of the
        request has been received.

        """
        super().post()

        filesize = os.stat(self.package_name).st_size
        self.log.debug('wrote {} bytes to {}'.format(filesize, self.package_name))

        self.application.onboard(
                self.package_name,
                self.boundary,
                self.transaction_id,
                auth=self.request.headers.get('authorization', None),
                )

        self.set_status(200)
        self.write(tornado.escape.json_encode({
            "transaction_id": self.transaction_id,
                }))


class UpdateHandler(StreamingUploadHandler):
    def msg_missing_account(self):
        return UpdateMissingAccount()

    def msg_missing_content_type(self):
        return UpdateMissingContentType()

    def msg_unsupported_media_type(self):
        return UpdateUnsupportedMediaType()

    def msg_missing_content_boundary(self):
        return UpdateMissingContentBoundary()

    def msg_start(self):
        return UpdateStart()

    def msg_success(self):
        return UpdateSuccess()

    def msg_failure(self):
        return UpdateFailure()

    def msg_package_upload(self):
        return UpdatePackageUpload()

    def post(self):
        """Handle a post request

        The function is called after any data associated with the body of the
        request has been received.

        """
        super().post()

        filesize = os.stat(self.package_name).st_size
        self.log.debug('wrote {} bytes to {}'.format(filesize, self.package_name))

        self.application.update(
                self.package_name,
                self.boundary,
                self.transaction_id,
                auth=self.request.headers.get('authorization', None),
                )

        self.set_status(200)
        self.write(tornado.escape.json_encode({
            "transaction_id": self.transaction_id,
                }))


class StateHandler(RequestHandler):
    def initialize(self, log, loop):
        self.log = log
        self.loop = loop

    def success(self, messages):
        success = self.__class__.SUCCESS
        return any(isinstance(msg, success) for msg in messages)

    def failure(self, messages):
        failure = self.__class__.FAILURE
        return any(isinstance(msg, failure) for msg in messages)

    def started(self, messages):
        started = self.__class__.STARTED
        return any(isinstance(msg, started) for msg in messages)

    def status(self, messages):
        if self.failure(messages):
            return "failure"
        elif self.success(messages):
            return "success"
        return "pending"

    def notifications(self, messages):
        notifications = {
                "errors": list(),
                "events": list(),
                "warnings": list(),
                }

        for msg in messages:
            if isinstance(msg, message.StatusMessage):
                notifications["events"].append({
                    'value': msg.name,
                    'text': msg.text,
                    'timestamp': msg.timestamp,
                    })
                continue

            elif isinstance(msg, message.WarningMessage):
                notifications["warnings"].append({
                    'value': msg.text,
                    'timestamp': msg.timestamp,
                    })
                continue

            elif isinstance(msg, message.ErrorMessage):
                notifications["errors"].append({
                    'value': msg.text,
                    'timestamp': msg.timestamp,
                    })
                continue

            self.log.warning('unrecognized message: {}'.format(msg))

        return notifications

    def get(self, transaction_id):
        if transaction_id not in self.application.messages:
            raise tornado.web.HTTPError(404, "unrecognized transaction ID")

        messages = self.application.messages[transaction_id]
        messages.sort(key=lambda m: m.timestamp)

        if not self.started(messages):
            raise tornado.web.HTTPError(404, "unrecognized transaction ID")

        notifications = self.notifications(messages)
        notifications["status"] = self.status(messages)

        self.write(tornado.escape.json_encode(notifications))


class ExportStateHandler(StateHandler):
    STARTED = ExportStart
    SUCCESS = ExportSuccess
    FAILURE = ExportFailure


class UploadStateHandler(StateHandler):
    STARTED = OnboardStart
    SUCCESS = OnboardSuccess
    FAILURE = OnboardFailure


class UpdateStateHandler(StateHandler):
    STARTED = UpdateStart
    SUCCESS = UpdateSuccess
    FAILURE = UpdateFailure


class UpdatePackage(threading.Thread):
    def __init__(self, log, app, accounts, filename, boundary, pkg_id, auth, use_ssl , ssl_cert, ssl_key):
        super().__init__()
        self.app = app
        self.log = log
        self.auth = auth
        self.pkg_id = pkg_id
        self.accounts = accounts
        self.filename = filename
        self.boundary = boundary
        self.updates_dir = os.path.join(
                os.environ['RIFT_ARTIFACTS'],
                "launchpad/updates",
                )
        self.pkg_dir = os.path.join(
                self.updates_dir,
                self.pkg_id,
                )
        self.use_ssl = use_ssl
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key

        # Get the IO loop from the import main thred
        self.io_loop = tornado.ioloop.IOLoop.current()

    def run(self):
        try:
            arch = self.extract_package()
            self.validate_images(arch)
            self.validate_descriptors(arch)

            try:
                self.update_images(arch)
            finally:
                self.remove_images(arch)

            self.update_descriptors(arch)

            self.log.message(UpdateSuccess())

        except MessageException as e:
            self.log.message(e.msg)
            self.log.message(UpdateFailure())

        except Exception as e:
            self.log.exception(e)
            if str(e):
                self.log.message(UpdateError(str(e)))
            self.log.message(UpdateFailure())

        finally:
            self.remove_images(arch)
            os.remove(self.filename)

    def validate_images(self, arch):
        for filename in arch.images:
            with open(os.path.join(self.pkg_dir, filename), 'r+b') as fp:
                chksum = checksums.checksum(fp)

            if chksum != arch.checksums[filename]:
                raise MessageException(UpdateChecksumMismatch(filename))

    def remove_images(self, arch):
        pkg_dir = os.path.join(os.environ['RIFT_ARTIFACTS'], 'launchpad/packages', self.pkg_id)
        for image in arch.images:
            try:
                os.remove(os.path.join(pkg_dir, image))
            except OSError:
                pass

    def validate_descriptors(self, arch):
        if not isinstance(arch, archive.DescriptorFile):
            # Checksum file is available only when a package is updated.
            # It is not available when a XML/JSON file is directly updated
            self.validate_descriptor_checksums(arch)

        self.validate_descriptor_existence(arch)

    def validate_descriptor_checksums(self, arch):
        def checksum_comparison(filename):
            with open(os.path.join(self.pkg_dir, filename), 'r+b') as fp:
                chksum = checksums.checksum(fp)

            if chksum != arch.checksums[filename]:
                raise MessageException(UpdateChecksumMismatch(filename))

        for filename in arch.vnfds:
            checksum_comparison(filename)

        for filename in arch.nsds:
            checksum_comparison(filename)

    def validate_descriptor_existence(self, arch):
        def validate_descriptor_existence_vnfd():
            serializer = convert.VnfdSerializer()

            descriptor_ids = set()
            for desc in self.app.tasklet.vnfd_catalog_handler.reg.elements:
                self.log.debug("validating descriptor: {}".format(desc.id))
                descriptor_ids.add(desc.id)

            for filename in arch.vnfds:
                # Read the VNFD from file
                filepath = os.path.join(self.pkg_dir, filename)

                vnfd = serializer.from_file(filepath)
                if vnfd.id not in descriptor_ids:
                    raise MessageException(UpdateNewDescriptor(filename))

        def validate_descriptor_existence_nsd():
            serializer = convert.NsdSerializer()

            descriptor_ids = set()
            for desc in self.app.tasklet.nsd_catalog_handler.reg.elements:
                self.log.debug("validating descriptor: {}".format(desc.id))
                descriptor_ids.add(desc.id)

            for filename in arch.nsds:
                # Read the NSD from file
                filepath = os.path.join(self.pkg_dir, filename)

                nsd = serializer.from_file(filepath)
                if nsd.id not in descriptor_ids:
                    raise MessageException(UpdateNewDescriptor(filename))

        done = threading.Condition()
        error = None

        # Define a callback that can be executed in the main thread in order to
        # safely interact with the tasklet
        def callback():
            nonlocal error

            done.acquire()

            try:
                validate_descriptor_existence_vnfd()
                validate_descriptor_existence_nsd()

            except MessageException as e:
                error = e

            except Exception as e:
                error = UpdateError(str(e))

            finally:
                done.notify()
                done.release()

        self.io_loop.add_callback(callback)

        done.acquire()
        done.wait()
        done.release()

        if error is not None:
            raise error

    def update_images(self, arch):
        if not arch.images:
            return

        self.log.debug("cloud accounts: {}".format(self.accounts))

        pkg_dir = os.path.join(os.environ['RIFT_ARTIFACTS'], 'launchpad/packages', self.pkg_id)

        account_images = {}
        for account in self.accounts:
            self.log.debug("getting image list for account {}".format(account.name))
            account_images[account] = []
            try:
                account_images[account] = account.get_image_list()
            except rift.mano.cloud.CloudAccountCalError as e:
                self.log.warning("could not get image list for account {}".format(account.name))
                continue

        for filename in arch.images:
            self.log.debug('uploading image: {}'.format(filename))

            image = rwcal.ImageInfoItem()
            image.name = os.path.basename(filename)
            image.location = os.path.join(pkg_dir, filename)
            image.checksum = arch.checksums[filename]

            for account in self.accounts:
                # Find images on the cloud account which have the same name
                matching_images = [i for i in account_images[account] if i.name == image.name]
                matching_checksum = [i for i in matching_images if i.checksum == image.checksum]
                if len(matching_checksum) > 0:
                    self.log.debug("found matching image with checksum, not uploading to {}".format(account.name))
                    continue

                self.log.debug("uploading to account {}: {}".format(account.name, image))
                try:
                    image.id = account.create_image(filename)
                except rift.mano.cloud.CloudAccountCalError as e:
                    self.log.error("error when uploading image {} to cloud account: {}".format(
                                   filename, str(e)))
                else:
                    self.log.debug('uploaded image to account{}: {}'.format(account.name, filename))

        self.log.message(OnboardImageUpload())

    def update_descriptors(self, arch):
        self.update_descriptors_vnfd(arch)
        self.update_descriptors_nsd(arch)

        self.log.message(UpdateDescriptorUpdated())
        self.log.debug("update complete")

    def update_descriptors_vnfd(self, arch):
        serializer = convert.VnfdSerializer()

        auth = ('admin', 'admin')

        for filename in arch.vnfds:
            # Read the descriptor from file
            filepath = os.path.join(self.pkg_dir, filename)
            try:
                vnfd_msg = serializer.from_file(filepath)
            except convert.UnknownExtensionError:
                raise MessageException(UpdateDescriptorFormatError(filename))

            vnfd_json = serializer.to_json_string(vnfd_msg)
            headers = {"content-type": "application/vnd.yang.data+json"}

            # Add authorization header if it has been specified
            if self.auth is not None:
                headers['authorization'] = self.auth

            url = "{}://127.0.0.1:8008/api/config/vnfd-catalog/vnfd/{}".format(
                    "https" if self.use_ssl else "http",
                    vnfd_msg.id
                    )
            try:
                response = requests.put(
                    url,
                    data=vnfd_json,
                    headers=headers,
                    auth=auth,
                    verify=False,
                    cert=(self.ssl_cert, self.ssl_key) if self.use_ssl else None,
                    timeout=5,
                    )

            except requests.Timeout:
                raise MessageException(UpdateDescriptorTimeout())

            if not response.ok:
                self.log.error(response.text)
                raise MessageException(UpdateDescriptorError(filename))

            self.log.debug('successfully updated: {}'.format(filename))

    def update_descriptors_nsd(self, arch):
        serializer = convert.NsdSerializer()

        auth = ('admin', 'admin')

        for filename in arch.nsds:
            # Read the NSD from file
            filepath = os.path.join(self.pkg_dir, filename)
            nsd_msg = serializer.from_file(filepath)

            nsd_json = serializer.to_json_string(nsd_msg)
            headers = {"content-type": "application/vnd.yang.data+json"}

            # Add authorization header if it has been specified
            if self.auth is not None:
                headers['authorization'] = self.auth

            # Send request to restconf

            url = "{}://127.0.0.1:8008/api/config/nsd-catalog/nsd/{}".format(
                    "https" if self.use_ssl else "http",
                    nsd_msg.id
                    )

            try:
                response = requests.put(
                    url,
                    data=nsd_json,
                    headers=headers,
                    auth=auth,
                    verify=False,
                    cert=(self.ssl_cert, self.ssl_key) if self.use_ssl else None,
                    timeout=5,
                )

            except requests.Timeout:
                raise MessageException(UpdateDescriptorTimeout())

            if not response.ok:
                self.log.error(response.text)
                raise MessageException(UpdateDescriptorError(filename))

            self.log.debug('successfully updated: {}'.format(filename))

    def extract_package(self):
        """Extract multipart message from tarball"""

        file_uploaded = None
        # Ensure the updates directory exists
        try:
            os.makedirs(self.updates_dir, exist_ok=True)
        except FileExistsError as e:
            pass

        pkgpath = os.path.join(self.updates_dir, self.pkg_id)
        pkgfile = pkgpath + ".tar.gz"
        with open(self.filename, 'r+b') as fp:
            file_uploaded = extract_package(self.log, fp, self.boundary, pkgfile)

        if file_uploaded is None:
            raise MessageException(UpdateUnreadablePackage())

        # Process the package archive
        if tarfile.is_tarfile(pkgfile):
            # Updated package was in a .tar.gz format
            tar = tarfile.open(pkgfile, mode="r:gz")
            arc = archive.LaunchpadArchive(tar, self.log)
        elif convert.ProtoMessageSerializer.is_supported_file(file_uploaded):
            # Updated file was a plain XML/JSON/YAML file
            arc = archive.DescriptorFile(self.log, file_uploaded, pkgfile)
        else:
            raise MessageException(UpdateUnreadablePackage())

        self.log.debug("archive extraction complete")
        arc.extract(pkgpath)

        return arc


class OnboardPackage(threading.Thread):
    def __init__(self, log, app, accounts, filename, boundary, pkg_id, auth, use_ssl, ssl_cert, ssl_key):
        super().__init__()
        self.app = app
        self.log = log
        self.auth = auth
        self.pkg_id = pkg_id
        self.accounts = accounts
        self.filename = filename
        self.boundary = boundary
        self.io_loop = tornado.ioloop.IOLoop.current()
        self.use_ssl = use_ssl
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key

    def run(self):
        try:
            arch = self.extract_package()

            try:
                self.upload_images(arch)
            finally:
                self.remove_images(arch)

            self.upload_libs(arch)

            self.onboard_descriptors(arch)

            self.log.message(OnboardSuccess())

        except MessageException as e:
            self.log.message(e.msg)
            self.log.message(OnboardFailure())

        except Exception as e:
            self.log.exception(e)
            if str(e):
                self.log.message(OnboardError(str(e)))
            self.log.message(OnboardFailure())

        finally:
            os.remove(self.filename)

    def remove_images(self, arch):
        pkg_dir = os.path.join(os.environ['RIFT_ARTIFACTS'], 'launchpad/packages', self.pkg_id)
        for image in arch.images:
            try:
                os.remove(os.path.join(pkg_dir, image))
            except OSError:
                pass

    def upload_images(self, arch):
        if not arch.images:
            return

        self.log.debug("cloud accounts: {}".format(self.accounts))

        pkg_dir = os.path.join(os.environ['RIFT_ARTIFACTS'], 'launchpad/packages', self.pkg_id)

        account_images = {}
        for account in self.accounts:
            self.log.debug("getting image list for account {}".format(account.name))
            account_images[account] = []
            try:
                account_images[account] = account.get_image_list()
            except rift.mano.cloud.CloudAccountCalError as e:
                self.log.warning("could not get image list for account {}".format(account.name))
                continue

        for filename in arch.images:
            self.log.debug('uploading image: {}'.format(filename))

            image = rwcal.ImageInfoItem()
            image.name = os.path.basename(filename)
            image.location = os.path.join(pkg_dir, filename)
            image.checksum = arch.checksums[filename]

            for account in self.accounts:
                # Find images on the cloud account which have the same name
                matching_images = [i for i in account_images[account] if i.name == image.name]
                matching_checksum = [i for i in matching_images if i.checksum == image.checksum]
                if len(matching_checksum) > 0:
                    self.log.debug("found matching image with checksum, not uploading to {}".format(account.name))
                    continue

                self.log.debug("uploading to account {}: {}".format(account.name, image))
                try:
                    image.id = account.create_image(image)
                except rift.mano.cloud.CloudAccountCalError as e:
                    self.log.error("error when uploading image {} to cloud account: {}".format(
                                   filename, str(e)))
                else:
                    self.log.debug('uploaded image to account{}: {}'.format(account.name, filename))

        self.log.message(OnboardImageUpload())

    def upload_libs(self, arch):
        if not arch.libs:
            return

        artifacts_dir = os.getenv('RIFT_ARTIFACTS', '/var/run/rift')
        libs_dir = os.path.join(artifacts_dir, 'launchpad/packages', self.pkg_id)
        install_dir = os.path.join(artifacts_dir, 'launchpad')
        try:
            for fname in arch.libs:
                fpath = os.path.join(install_dir, os.path.dirname(fname))
                os.makedirs(fpath, exist_ok=True)
                self.log.debug("%s: Copy file %s to %s" %
                               (self.pkg_id, fname, fpath))
                shutil.copy(os.path.join(libs_dir, fname), fpath)

        except Exception as e:
            self.log.error("Exception moving files for package {}: {}".
                           format(self.pkg_id, e))
            self.log.exception(e)
            raise e


    def onboard_descriptors(self, arch):

        pkg_dir = os.path.join(os.environ['RIFT_ARTIFACTS'], "launchpad/packages", self.pkg_id)

        def post(url, data, headers):
            auth = ('admin', 'admin')

            try:
                if self.use_ssl:
                    response = requests.post(
                            url,
                            data=data,
                            headers=headers,
                            auth=auth,
                            verify=False,
                            cert=(self.ssl_cert, self.ssl_key),
                            timeout=5,
                            )
                else:
                    response = requests.post(
                            url,
                            data=data,
                            headers=headers,
                            auth=auth,
                            timeout=5,
                            )
            except requests.Timeout:
                raise MessageException(OnboardDescriptorTimeout())

            if not response.ok:
                self.log.error(response.text)
                raise MessageException(OnboardDescriptorError(filename))

            self.log.debug('successfully uploaded: {}'.format(filename))

        self.log.message(OnboardDescriptorValidation())

        endpoints = (
                ("vnfd-catalog/vnfd", arch.vnfds, convert.VnfdSerializer()),
                ("pnfd-catalog/pnfd", arch.pnfds, convert.PnfdSerializer()),
                ("vld-catalog/vld", arch.vlds, convert.VldSerializer()),
                ("nsd-catalog/nsd", arch.nsds, convert.NsdSerializer()),
                ("vnffgd-catalog/vnffgd", arch.vnffgds, convert.VnffgdSerializer()),
                )

        try:
            for catalog, filenames, serializer in endpoints:
                for filename in filenames:
                    filepath = os.path.join(pkg_dir, filename)

                    try:
                        msg = serializer.from_file(filepath)
                    except convert.UnknownExtensionError:
                        raise MessageException(OnboardDescriptorFormatError(filename))

                    # Regardless of the input serialized format, re-serialize to JSON
                    # so there is a single code-path through RESTCONF
                    json_data = serializer.to_json_string(msg)
                    headers = {"content-type": "application/vnd.yang.data+json"}

                    # Add authorization header if it has been specified
                    if self.auth is not None:
                        headers['authorization'] = self.auth

                    url = "{}://127.0.0.1:8008/api/config/{}".format(
                            "https" if self.use_ssl else "http",
                            catalog
                            )

                    post(url, json_data, headers)

            self.log.message(OnboardDescriptorOnboard())
            self.log.debug("onboard complete")

        except Exception:
            # TODO: At this point we need to roll back all of the descriptors
            # that were successfully onboarded.
            self.log.error("Unable to onboard {}".format(filename))
            raise

    def extract_package(self):
        """Extract multipart message from tarball"""

        # Ensure the packages directory exists
        packages = os.path.join(os.environ["RIFT_ARTIFACTS"], "launchpad/packages")
        file_uploaded = None
        try:
            os.makedirs(packages, exist_ok=True)
        except FileExistsError as e:
            pass

        pkgpath = os.path.join(packages, self.pkg_id)

        pkgfile = pkgpath + ".tar.gz"
        with open(self.filename, 'r+b') as fp:
            file_uploaded = extract_package(self.log, fp, self.boundary, pkgfile)

        if file_uploaded is None:
            raise MessageException(OnboardUnreadablePackage())

        # Process the package archive
        if ToscaPackage.is_tosca_package(pkgfile):
            # This could be a tosca package, try processing
            tosca = ToscaPackage(self.log, pkgfile)
            if tosca.translate() is None:
                raise MessageException("Could not process as a "
                                        "TOSCA package {}".format(pkgfile))
            else:
                self.log.info("Tosca package was translated successfully")
                # Fall through to process a YANG descriptor
        if tarfile.is_tarfile(pkgfile):
            # Uploaded package was in a .tar.gz format
            tar = tarfile.open(pkgfile, mode="r:gz")
            arc = archive.LaunchpadArchive(tar, self.log)
        elif convert.ProtoMessageSerializer.is_supported_file(file_uploaded):
            # Uploaded file was a plain XML/JSON file
            arc = archive.DescriptorFile(self.log, file_uploaded, pkgfile)
        else:
            raise MessageException(OnboardUnreadablePackage())

        self.log.debug("archive extraction complete")
        arc.extract(pkgpath)
        return arc


class ExportHandler(RequestHandler):
    def initialize(self, log, loop):
        self.loop = loop
        self.transaction_id = str(uuid.uuid4())
        self.log = message.Logger(
                log,
                self.application.messages[self.transaction_id],
                )

    def get(self):
        self.log.message(ExportStart())

        # Parse the IDs
        ids_query = self.get_query_argument("ids")
        ids = [id.strip() for id in ids_query.split(',')]

        # Retrieve the list of the descriptors
        descriptors = list()
        for id in ids:
            if id in self.application.vnfd_catalog:
                descriptors.append(self.application.vnfd_catalog[id])
                continue

            if id in self.application.nsd_catalog:
                descriptors.append(self.application.nsd_catalog[id])
                continue

            raise tornado.web.HTTPError(400, "unknown descriptor: {}".format(id))

        pkg = archive.PackageArchive()

        # Add the VNFDs to the package
        for desc in descriptors:
            if isinstance(desc, VnfdYang.YangData_Vnfd_VnfdCatalog_Vnfd):
                pkg.add_vnfd(desc)

        # Add any NSDs to the package
        for desc in descriptors:
            if isinstance(desc, NsdYang.YangData_Nsd_NsdCatalog_Nsd):
                pkg.add_nsd(desc)

        # Create a closure to create the actual package and run it in a
        # separate thread
        pkg.create_archive(
                self.transaction_id,
                dest=self.application.export_dir,
                )

        self.log.message(ExportSuccess())

        self.write(tornado.escape.json_encode({
            "transaction_id": self.transaction_id,
                }))


class UploaderApplication(tornado.web.Application):
    def __init__(self, tasklet):
        self.tasklet = tasklet
        self.accounts = []
        self.messages = collections.defaultdict(list)
        self.export_dir = os.path.join(os.environ['RIFT_ARTIFACTS'], 'launchpad/exports')

        manifest = tasklet.tasklet_info.get_pb_manifest()
        self.use_ssl = manifest.bootstrap_phase.rwsecurity.use_ssl
        self.ssl_cert = manifest.bootstrap_phase.rwsecurity.cert
        self.ssl_key = manifest.bootstrap_phase.rwsecurity.key

        attrs = dict(log=self.log, loop=self.loop)

        super(UploaderApplication, self).__init__([
            (r"/api/update", UpdateHandler, attrs),
            (r"/api/upload", UploadHandler, attrs),
            (r"/api/export", ExportHandler, attrs),
            (r"/api/upload/([^/]+)/state", UploadStateHandler, attrs),
            (r"/api/update/([^/]+)/state", UpdateStateHandler, attrs),
            (r"/api/export/([^/]+)/state", ExportStateHandler, attrs),
            (r"/api/export/([^/]+.tar.gz)", tornado.web.StaticFileHandler, {
                "path": self.export_dir,
                })
            ])

    @property
    def log(self):
        return self.tasklet.log

    @property
    def loop(self):
        return self.tasklet.loop

    def get_logger(self, transaction_id):
        return message.Logger(self.log, self.messages[transaction_id])

    def onboard(self, package, boundary, transaction_id, auth=None):
        log = message.Logger(self.log, self.messages[transaction_id])

        pkg_id = str(uuid.uuid1())
        OnboardPackage(
                log,
                self,
                self.accounts,
                package,
                boundary,
                pkg_id,
                auth,
                self.use_ssl,
                self.ssl_cert,
                self.ssl_key,
                ).start()

    def update(self, package, boundary, transaction_id, auth=None):
        log = message.Logger(self.log, self.messages[transaction_id])

        pkg_id = str(uuid.uuid1())
        UpdatePackage(
                log,
                self,
                self.accounts,
                package,
                boundary,
                pkg_id,
                auth,
                self.use_ssl,
                self.ssl_cert,
                self.ssl_key,
                    ).start()

    @property
    def vnfd_catalog(self):
        return self.tasklet.vnfd_catalog

    @property
    def nsd_catalog(self):
        return self.tasklet.nsd_catalog

    @property
    def vld_catalog(self):
        return self.tasklet.vld_catalog

    def get_vlds(self, vld_ids):
        vlds = list()
        for id in vld_ids:
            vlds.append(self.vld_catalog[id])

        return vlds
