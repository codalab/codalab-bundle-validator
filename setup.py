from os import path
from setuptools import setup

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='codalab_yaml_validator',
    packages=['codalab_yaml_validator'],
    install_requires=[
        "yamale==1.10.0",
        "python-dateutil==2.8.0",
        "fuzzywuzzy==0.17.0",
        "python-Levenshtein==0.12.0",
    ],
    entry_points={
        'console_scripts': [
            'validate_bundle = codalab_yaml_validator.yaml_validator:main',
        ]
    },
    license="MIT",
    long_description=long_description,
    long_description_content_type='text/markdown',
    version='0.0.10',
    url='https://github.com/codalab/codalab-bundle-validator',
    include_package_data=True,
    python_requires='>=3'
)
