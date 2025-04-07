# W'+b

Python package for analyzing H+c events. The package uses a columnar framework to process input tree-based NanoAOD V12 files using [Coffea](https://coffeateam.github.io/coffea/) and [scikit-hep](https://scikit-hep.org) Python libraries.

- [Workflows](#Workflows)
- [Input filesets](#Input-filesets)
- [Submit Condor jobs](#Submit-Condor-jobs)
- [Postprocessing](#Postprocessing)

### Workflows

The available workflows are:

* [ztomumu](https://github.com/deoache/wprimeplusb/blob/main/analysis/workflows/ztomumu.yaml)
* [ztoee](https://github.com/deoache/wprimeplusb/blob/main/analysis/workflows/ztoee.yaml)
* [2b1mu](https://github.com/deoache/wprimeplusb/blob/main/analysis/workflows/2b1mu.yaml)
* [2b1e](https://github.com/deoache/wprimeplusb/blob/main/analysis/workflows/2b1e.yaml)


The workflows (selections, variables, output histograms, triggers, etc) are defined through a configuration file located in `analysis/workflows`. [Here](https://github.com/deoache/wprimeplusb/blob/main/analysis/workflows/README.md) you can find a detailed description on how to create the config file.


### Input filesets

Each year has a config file in `analysis/filesets/<year>_nanov9.yaml` from which the input filesets are built. The sites allowed are defined in [`analysis/filesets/xrootd_sites.py`](https://github.com/deoache/higgscharm/blob/lxplus/analysis/filesets/xrootd_sites.py).


### Submit Condor jobs

First connect to lxplus and clone the repository (if you have not done it yet)
```
ssh <your_username>@lxplus.cern.ch

git clone https://github.com/deoache/wprimeplusb.git
cd wprimeplusb
```
You need to have a valid grid proxy in the CMS VO. (see [here](https://twiki.cern.ch/twiki/bin/view/CMSPublic/SWGuideLcgAccess) for details on how to register in the CMS VO). The needed grid proxy is obtained via the usual command
```
voms-proxy-init --voms cms
```
Jobs are submitted via the [submit_condor.py](https://github.com/deoache/higgscharm/blob/lxplus/submit_condor.py) script
```
python3 submit_condor.py --workflow ztomumu --dataset ZZ --year 2017 --submit --eos
```
**Note**: It's recommended to add the `--eos` flag to save the outputs in your `/eos` area, so the postprocessing step can be done from [SWAN](https://swan-k8s.cern.ch/hub/spawn). **In this case, you will need to clone the repo also in [SWAN](https://swan-k8s.cern.ch/hub/spawn) (select the 105a release) in order to be able to run the postprocess**.

The [runner.py](https://github.com/deoache/higgscharm/blob/lxplus/runner.py) script is built on top of `submit_condor.py` and can be used to submit all jobs (MC + data) of a workflow/year
```
python3 runner.py --workflow ztomumu --year 2017 --submit --eos
``` 
After submitting the jobs you can watch their status by typing:
```
watch condor_q
```
You can use the `jobs_status.py` script to see which jobs are still to be executed, build new datasets in case there are xrootd OS errors, update and resubmit condor jobs.
```
python3 jobs_status.py --workflow ztomumu --year 2017 --eos
```

### Postprocessing

Once all jobs are done for a processor/year, you can get the results using the `run_postprocess.py` script:
```
python3 run_postprocess.py --workflow ztomumu --year 2017 --postprocess --plot --log
``` 
Results will be saved to the same directory as the output files