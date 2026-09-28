The HRRR and GFS live checks open GRIB2 files with open_grib2, which pyright can check, after the old dynamic open(select=...) call broke the weekly run; no package change.
