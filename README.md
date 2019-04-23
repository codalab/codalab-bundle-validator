# Codalab Yaml Validator
Codalab Yaml Validator is a command line tool made to be used in conjunction with Codalab V2. It validates competition
bundles locally without having to upload to the server first. It can also be used to compare one bundle to another, and
show the differences between them. Functionally, this is aimed at comparing a bundle used to upload a competition with
a dump of that competition created by the server, used to point out any differences between the two. This can be used
both to validate that changes _have not_ been made during the upload process, and also to validate that any changes
made in the editor on the server _have_ been accounted for in the dumps file.

## Installation
Using `pip`
```bash
pip install codalab_yaml_validator
```

## Usage
### Single Directory Validation
This can be used to validate a folder or a .zip file.
```bash
# Validating a folder
validate_bundle /path/to/folder/

# Validating a zip file
validate_bundle /path/to/file.zip
```

#### Output
First, the yaml file `competition.yaml` is run through an initial formatting validation. This is done using the expected
schema (provided below). If there are errors on this level, a `ValueError` is raised and the validation process stops.
##### Example error message
```
Traceback
...
ValueError: 
Error validating data /.../competition.yaml with schema /.../site-packages/codalab_yaml_validator/schema.yaml
	tasks.0.index: Required field missing
```
If the first validation process is passed, `Yaml file passed initial formatting tests` is printed and a deeper validation
process begins. This verifies things like the same index is not used on multiple phases, or that the files provided for
this like images and scoring programs actually exist at the provided file path. In this process there are both `Errors`
and `Warnings`. Errors will prevent a bundle from being valid, and thus cannot be uploaded to Codalab, while warnings
are not invalid bundles, but uploading the bundle may not produce the desired competition.
##### Example
```
WARNINGS:
- Task with index 0: If specifying a key, all other fields will be ignored on upload
ERRORS:
- Duplicate task index(es): [0]
- Task index: "1" on phase: "Example Phase Name" not present in tasks
- File for scoring_program - (path/to/scoring_program.zip) - not found
```

If there are no errors `Yaml bundle is valid` will be printed

### Bundle to Bundle Comparison
```bash
validate_bundle /path/to/bundle/one /path/to/bundle/two
```
Just as before, both directories and zip files are acceptable, and one can be compared to the other, i.e.,
```bash
validate_bundle /path/to/zip.zip /path/to/folder
```

Bundles are each run through the single bundle validation before comparisons are made. If either bundle is invalid,
the comparisons will not be made and errors must be addressed. If no errors are present, comparison will begin.
<br>
Note: This validation is run silently, so warnings will not be printed, nor will validity affirmations. The only
feedback that will be printed are errors to be addressed.

If both bundles are valid, comparisons will be made. Because the competition editor on Codalab allows for changing every
value present in an upload bundle, and the dumps process may print things like Tasks in different orders than they were
uploaded in, there is no definitive way to _know_ which Task originated with which. This comparison process examines all
possible options and compares the ones that match the closest. 

For example, if the upload bundle looks like:
```yaml
# ...
phases:
- index: 0
  name: Fast Phase
  description: Computing Pi Faster
  start: 02-01-2019
  end: 09-01-2019
  tasks:
  - 1
- index: 1
  name: Slower Phase
  description: Computing Pi
  start: 08-01-2018
  end: 02-01-2019
  tasks:
  - 0
# ...
```
And the dump bundle looks something like:
```yaml
# ...
phases:
- index: 0
  name: Slow Phase
  description: Computing Pi
  start: 08-01-2018
  end: 02-01-2019
  tasks:
  - 0
- index: 1
  name: Fast Phase
  description: Computing Pi Quickly
  start: 02-01-2019
  end: 09-01-2019
  tasks:
  - 1
# ...
```

The Comparison process can intelligently determine that index 0 in the upload bundle should be compared to index 1 in the
dump bundle, so that the most accurate account of differences can be given. This does have some limitations, especially 
as the number of changes made in the editor increase, but it should seek to minimize the number of differences when
making comparisons. This process is the same for comparing tasks, solutions, leaderboards, and columns.

##### Example Output
In the case of the above yamls:
```
$ validate_bundle /path/to/Archive/ /path/to/Dump.zip
Differences:

- Values on Phases index:1 in Archive and index:0 in Dump.zip do not match for key: name.
  - Archive = Slower Phase
  - Dump.zip = Slow Phase

- Values on Phases index:0 in Archive and index:1 in Dump.zip do not match for key: description.
  - Archive = Computing Pi Faster
  - Dump.zip = Computing Pi Quickly
```

##### Limitations
Codalab allows uploading things like scoring programs in unzipped directories and zips them itself during the
upload process. When a dump is created, these zipped directories are returned. Hashes are used to compare files like this
so the folder must be compressed and then hashed. The compression of this directory yields a different hash than its
already compressed counterpart, so these files must be validated manually.

While a bundle using the same hierarchy as Codalab v1.5 is currently acceptable to upload to Codalab v2, its validation
is outside the scope of this tool. Bundle must be of the "Task Solution" style to be validated properly.

EOFs on pages are changed in the process of storing their content as text on the server, so when a dump of that content
is created, even if the characters are the same, the contents of the file differ slightly so verifying these with a
hash is impossible. Again, these files will need to be checked manually. Because every page would be flagged as different,
pages are not checked for differences at all.
