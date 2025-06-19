<div align="center">
  <img src="https://github.com/harvardinformatics/cactus-snakemake/blob/main/etc/logo/cactus-snakemake-hex.png" style="height: 200px;"/>
</div>

<div align="center">
  <a href="https://doi.org/10.5281/zenodo.15699752"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.15699752.svg" alt="DOI"></a>
</div>

### These pipelines facilitate the running of the [Cactus whole genome alignment tool](https://github.com/ComparativeGenomicsToolkit/cactus) efficiently on SLURM (and possibly other) clusters.

## Tutorials available on the [FAS Informatics website](https://informatics.fas.harvard.edu/):

### <[Whole genome alignment with Progressive Cactus](https://informatics.fas.harvard.edu/resources/Tutorials/whole-genome-alignment-cactus/)>

#### <[Adding a genome to a whole genome alignment](https://informatics.fas.harvard.edu/resources/Tutorials/add-to-whole-genome-alignment-cactus/)>

#### <[Adding an outgroup to a whole genome alignment](https://informatics.fas.harvard.edu/resources/Tutorials/add-outgroup-to-whole-genome-alignment-cactus/)>

#### <[Replacing a genome in a whole genome alignment](https://informatics.fas.harvard.edu/resources/Tutorials/replace-genome-whole-genome-alignment-cactus/)>

### <[Pangenome inference with Minigraph-Cactus](https://informatics.fas.harvard.edu/resources/Tutorials/pangenome-cactus-minigraph/)>

> ⚠️ **Important!** cactus-snakemake v3.0.0 and later requires Cactus v2.9.9 or later. 
>
> Due to bug fixes in Cactus, v3.0.0+ of cactus-snakemake is only compatibile with Cactus v2.9.9 or later. Don't worry, cactus-snakemake will always use the latest version of Cactus available unless you specify otherwise in your config file. However, if you do wish to use an older version of Cactus, you can use cactus-snakemake v2.1.0.

## Installation

Installation is done simply by cloning the repository:

```{bash}
git clone https://github.com/harvardinformatics/cactus-snakemake.git
```

Alternatively, you could just manually download the [latest release](https://github.com/harvardinformatics/cactus-snakemake/releases/latest) and unzip it and it should be good to go.

However, Snakemake and Singularity are required as dependencies. For more information, see the setup instructions in any of the tutorials linked above.

## Usage

Each pipeline has a different [config file](config-templates/) that is required to specify input and output options and cluster resources.

With the config file setup, the pipelines are generally run as:

```{bash}
snakemake -j <number of jobs to submit simultaneously> -e slurm -s </path/to/snakefile.smk> --configfile </path/to/your/snakmake-config.yml>
```


> 💡 **Tip:** Cannon cluster Snakemake plugin
>
> If you are on the Harvard Cannon cluster, you can use the [snakemake-executor-plugin-cannon](https://github.com/harvardinformatics/snakemake-executor-plugin-cannon) to do automatic partition selection instead of the generic SLURM executor plugin. Install the plugin with pip or mamba and then use `-e cannon` in all of your commands instead of `-e slurm`.


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

## Citation

If you use this software, please cite:

Thomas, G. (2025). Snakemake workflows for Cactus (Version 2.1.0) [Computer software]. 
[https://doi.org/10.5281/zenodo.15596990](https://doi.org/10.5281/zenodo.15596989)

> **To cite a specific version:**  
> See the [full list of versions and DOIs here](https://zenodo.org/records/15596990).  
> (Find the version you used in the Zenodo version history.)
