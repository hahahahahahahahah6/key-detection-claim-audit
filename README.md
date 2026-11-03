# Documentation claim auditor

This offline tool compares documentation statements with Python syntax evidence.
It never executes inspected source, makes no network requests, writes no files,
and collects no telemetry. Requires Python 3.9 or later.

Install and run:

```sh
python3 -m pip install .
key-detection-claim-audit ./project
python3 -m key_detection_claim_audit ./project --json
python3 -m key_detection_claim_audit ./project --verbose --ignore vendor --ignore build
python3 -m key_detection_claim_audit ./project --fail-on MEDIUM
python3 -m key_detection_claim_audit --version
```

The root README and Markdown files under any docs path component supply prose.
Fenced blocks are skipped; inline code counts. Paragraph matching ignores case,
expands negative contractions, replaces hyphens with spaces, and collapses
whitespace. Exact word boundaries apply, longer phrases first, with alphabetical
ties. Negative spans are removed before affirmative matching.

Source is parsed without execution. Evidence must occur in one module. Supported
constructions and generic call names are:

```text
essentia.KeyExtractor(), essentia.standard.KeyExtractor()
detect_key estimate_key get_key key_detect detect_musical_key
estimate_musical_key get_musical_key musical_key_detect identify_key
key_identify predict_key key_predict classify_key key_classify analyze_key
analyse_key extract_key key_extract detect_tonality estimate_tonality
get_tonality tonality_detect detect_key_signature estimate_key_signature
detect_tonic estimate_tonic
```

The library construction requires an imported binding. Generic attributes accept
any base; bare names require a resolved from-import. Local function and method
definitions shadow generic names. Imports alone, strings, bare references,
subprocess commands, invalid syntax, and adjacent operations supply no evidence.
Recognized syntax does not establish runtime correctness.

Symlinks are skipped. Files under fixtures, docs, and examples supply no evidence.
Conventional test filenames and files under tests supply only test evidence.
An unsupported affirmative statement produces a finding, reduced to medium
severity when evidence exists only in tests. A negative statement conflicting
with production evidence produces a high severity finding. Without source,
affirmative statements still produce findings and negative statements pass.

```text
documented-key-detection-claim-false       HIGH (MEDIUM for test evidence only)
documented-no-key-detection-claim-false    HIGH
```

JSON contains verdict, findings, document and source paths, and evidence flags.
Each finding has id, severity, and message fields. Any finding yields a FAIL
verdict. Exit status is 2 when a finding meets the threshold, 0 otherwise, and
1 for usage or I/O errors. The default threshold is HIGH; LOW and MEDIUM are
also accepted. Repeatable ignore options exclude relative path prefixes at
component boundaries. Verbose output includes inspected paths and evidence flags.

Development checks:

```sh
python3 -m unittest discover
python3 -m build
```

MIT licensed.
