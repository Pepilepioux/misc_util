# misc_util
Miscelaneous utilities that I don't know yet where to put precisely...

## gipkoutils

### chrono_trace

A decorator so see how much time is spent in a function

### conserver_dates

A decorator to allow modifying a file and reset its original mtime 

### expurge

A function that replaces all unicode characters (> 255) in a string with a printable character (default ¶) to prevent raising an exception
when attempting to print a text that contains some exotic unicode.

### Recepteur

A utility that listens a TCP port and triggers another program depending on the content of received data.
It has a few builtin features, like processing a stop order, returning some information and setting logging
level and 3 timeout values.

### dateIsoVersTimestamp, dateIsoVersTs, timestampVersDateIso, tsVersDateIso

Datetime conversion functions

## exemple_recepteur

An example how to use Recepteur.

## controleur

A small command line utility to send data to Recepteur

## vivant

A small program that listens to a TCP port and responds. For communication tests, or just to be able to remotely check whether a machine is
still alive. 

I used to have it running on a probe on my internal network, with the appropriate port opened in the firewall, just to make sure
from outside that the internet connection was OK.

## gipkoexif

Some functions to retrieve exif data from a photo file, especially the GPS coordinates.

## gipkogps

Miscelaneaous functions to handle gps data, tracks, calculate distances...

## Dependencies
* python 3 (developed and tested with python 3.4 through 3.8, depending on modules)
* Pillow (gipkoexif)
* xml, numpy (gipkogps)
* (some modules) gipkomail available [here] (https://github.com/Pepilepioux/server_stats/)


## License
This work is licensed under [Creative Commons Attribution-NonCommercial 4.0 International](https://creativecommons.org/licenses/by-nc/4.0/legalcode)

You are free to share and adapt it as long as you give appropriate credit, provide a link to the license and indicate if changes were made.

You may use it as you want as long as it is not for commercial purposes.

# Authors
* Pepilepioux
