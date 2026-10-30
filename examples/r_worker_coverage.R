# Local test driver. Actual native train/reload/scenario; never uploads coverage.
args <- commandArgs(trailingOnly=TRUE)
stopifnot(length(args)==1L)
project <- normalizePath(args[1],winslash="/",mustWork=TRUE)
.libPaths(c(file.path(project,"var/runtime/r-library"),.libPaths()))
Sys.setenv(RETICULATE_PYTHON=file.path(project,"var/envs/robyn",if(.Platform$OS.type=="windows")"Scripts/python.exe" else "bin/python"),RETICULATE_AUTOCONFIGURE="FALSE")
root <- file.path(project,"evidence/r-worker-coverage")
dir.create(root,recursive=TRUE,showWarnings=FALSE)
Sys.setenv(MMM_R_COVERAGE_INPUTS=file.path(project,"var/coverage/r-inputs"),
           MMM_R_COVERAGE_OUTPUT=root)
coverage <- covr::file_coverage(
  source_files=file.path(project,"src/mmm_intelligence/integrations/robyn_worker.R"),
  test_files=file.path(project,"tests/r/native_cases.R"))
saveRDS(coverage,file.path(root,"coverage.rds"))
jsonlite::write_json(list(line_percent=covr::percent_coverage(coverage),
                         source_sha256=digest::digest(file=file.path(project,"src/mmm_intelligence/integrations/robyn_worker.R"),algo="sha256"),
                         expression_counts=as.data.frame(coverage),
                         branch_percent=NULL,
                         limitations="covr measures R lines/expressions; branch instrumentation remains separate and is not certified by this percentage",
                         native_cases=c("train","predict","scenario")),
                    file.path(root,"coverage.json"),auto_unbox=TRUE,pretty=TRUE,null="null")
print(coverage)
measured <- as.data.frame(coverage)
stopifnot(nrow(measured)>0L,all(measured$value>0))
