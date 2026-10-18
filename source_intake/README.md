# Six-cohort source intake

The six user-supplied Freddie Mac sample ZIPs are read in place. Raw rows are
not extracted, republished or uploaded to GitHub. Each member is read completely
for its byte hash, ZIP CRC, schema, loan-key, calendar and duplicate checks.

```bash
python source_intake/audit_uploads.py --input-dir /absolute/path/to/your/samples
```

The reports contain aggregate integrity evidence. The 2012 archive and both
members must match the previously preserved snapshot exactly. No outcome-based
sample selection, model fitting or held-out performance evaluation occurs here.
This new intake code supplements the earlier frozen P1 work; it does not
reconstruct the absent 18-file cohort-builder checkpoint.

Source documentation: [Freddie Mac dataset](https://www.freddiemac.com/research/datasets/sf-loanlevel-dataset),
[Release 47 guide](https://www.freddiemac.com/fmac-resources/research/pdf/general_user_guide_july_2026.pdf),
and [dataset terms](https://capitalmarkets.freddiemac.com/crt/docs/pdfs/fre_terms_conditions_sflld.pdf).
Use is a noncommercial research study. Public source code and non-reconstructive
aggregate research results are separate from the provider's loan-level data.
The revised source is not an immutable historical-vintage snapshot.
