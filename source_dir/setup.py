from os import path
from setuptools import setup

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='codalab_yaml_validator',
    packages=['codalab_yaml_validator'],
    long_description=long_description,
    long_description_content_type='text/markdown',
    version='version number',
    author='',
    author_email='',
    url='https://github.com/asdf',
    download_url='download link?',
    classifiers=[],
)