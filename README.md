## Tutorials available on the [FAS Informatics website](https://informatics.fas.harvard.edu/):

### <[Whole genome alignment with Progressive Cactus](https://informatics.fas.harvard.edu/resources/Tutorials/whole-genome-alignment-cactus/)>

#### <[Adding a genome to a whole genome alignment](https://informatics.fas.harvard.edu/resources/Tutorials/add-to-whole-genome-alignment-cactus/)>

#### <[Adding an outgroup to a whole genome alignment](https://informatics.fas.harvard.edu/resources/Tutorials/add-outgroup-to-whole-genome-alignment-cactus/)>

#### <[Replacing a genome in a whole genome alignment](https://informatics.fas.harvard.edu/resources/Tutorials/replace-genome-whole-genome-alignment-cactus/)>

### <[Pangenome inference with Minigraph-Cactus](https://informatics.fas.harvard.edu/resources/Tutorials/pangenome-cactus-minigraph/)>

## Installation

Installation is done simply by cloning the repository:

```{bash}
git clone https://github.com/harvardinformatics/cactus-snakemake.git
```

However, Snakemake and Singularity are required as dependencies. For more information, see the setup instructions in any of the tutorials linked above.

## Usage

Each pipeline has a different [config file](config-templates/) that is required to specify input and output options and cluster resource specifications.

With the config file setup, the pipelines are generally run as:

```{bash}
snakemake -j <number of jobs to submit simultaneously> -e slurm -s </path/to/snakefile.smk> --configfile </path/to/your/snakmake-config.yml>
```

For more information, see the setup and run instructions in each of the tutorials linked above.

## Meta config options

Several meta config options exist across pipelines as pseudo-command line flags

| Command line flag    | Description |
| -------------------- | ----------- |
| `--config display=T` | Print the current config settings and exit |
| `--config info=T`    | Display some information about the pipelines, including version and last commit date |
| `--config version=T` | Display the version of the pipeline |
| `--config prep=T`    | Run all pre-processing steps and exit (*e.g.* output directory creation, cactus image download, running `cactus-prepare`). |
| `--config debug=T`   | The same as prep, but display extra information about the pre-processing steps. |
