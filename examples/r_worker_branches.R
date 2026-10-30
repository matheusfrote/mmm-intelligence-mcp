# Test-only AST instrumentation of every if and for in the actual R source.
# covr measures lines separately; this measures decision and loop body/exit branches.
args <- commandArgs(trailingOnly=TRUE)
stopifnot(length(args)==1L)
project <- normalizePath(args[1],winslash="/",mustWork=TRUE)
.libPaths(c(file.path(project,"var/runtime/r-library"),.libPaths()))
Sys.setenv(RETICULATE_PYTHON=file.path(project,"var/envs/robyn",if(.Platform$OS.type=="windows")"Scripts/python.exe" else "bin/python"),RETICULATE_AUTOCONFIGURE="FALSE")
Sys.setenv(R_LIBS_USER=file.path(project,"var/runtime/r-library"))
root <- file.path(project,"evidence/r-worker-branches")
dir.create(root,recursive=TRUE,showWarnings=FALSE)
source_path <- file.path(project,"src/mmm_intelligence/integrations/robyn_worker.R")
original <- parse(source_path,keep.source=TRUE)
definitions <- list()
walk <- function(node,context="top-level") {
  if(is.expression(node)) return(as.expression(lapply(node,walk,context=context)))
  if(!is.call(node)) return(node)
  head <- as.character(node[[1]])[1]
  if(head=="<-" && is.call(node[[3]]) && identical(node[[3]][[1]],as.name("function"))) {
    node[[3]] <- walk(node[[3]],as.character(node[[2]]))
    return(node)
  }
  for(i in seq_along(node)[-1L]) {
    if(!identical(node[[i]],quote(expr=))) node[i] <- list(walk(node[[i]],context))
  }
  if(head %in% c("if","for")) {
    id <- paste0("branch-",length(definitions)+1L)
    definitions[[id]] <<- list(kind=head,context=context,expression=paste(deparse(node),collapse=" "))
    if(head=="if") {
      node[[2]] <- call(".mmm_decision",id,node[[2]])
    } else {
      node[[4]] <- call("{",call(".mmm_mark",id,"true"),node[[4]])
      # Count exit only when control actually reaches the expression after the loop.
      return(call("{",node,call(".mmm_mark",id,"false")))
    }
  }
  node
}
instrumented <- walk(original)
template <- paste(capture.output(dput(definitions)),collapse="\n")
header <- c(paste0(".mmm_definitions <- ",template),
  '.mmm_counts <- new.env(parent=emptyenv())',
  'for(id in names(.mmm_definitions)) .mmm_counts[[id]] <- c(true=0L,false=0L)',
  '.mmm_destination <- Sys.getenv("MMM_R_BRANCH_JSON")',
  '.mmm_decision <- function(id,value) {',
  '  logical <- as.logical(value)',
  '  if(length(logical)==1L && !is.na(logical)) {',
  '    counts <- .mmm_counts[[id]]; key <- if(logical) "true" else "false"',
  '    counts[[key]] <- counts[[key]]+1L; .mmm_counts[[id]] <- counts',
  '  }; value',
  '}',
  '.mmm_mark <- function(id,key) {',
  '  counts <- .mmm_counts[[id]]; counts[[key]] <- counts[[key]]+1L',
  '  .mmm_counts[[id]] <- counts; invisible(NULL)',
  '}',
  '.mmm_write <- function() jsonlite::write_json(as.list(.mmm_counts),.mmm_destination,auto_unbox=TRUE,pretty=TRUE)',
  'reg.finalizer(.mmm_counts,function(e) .mmm_write(),onexit=TRUE)')
generated <- file.path(root,"instrumented-worker.R")
writeLines(c(header,unlist(lapply(instrumented,deparse))),generated)
parent_json <- file.path(root,"sourced-counts.json")
child_json <- file.path(root,"entrypoint-counts.json")
Sys.setenv(MMM_R_BRANCH_JSON=parent_json,
           MMM_R_COVERAGE_INPUTS=file.path(project,"var/coverage/r-inputs"),
           MMM_R_COVERAGE_OUTPUT=file.path(root,"cases"))
dir.create(Sys.getenv("MMM_R_COVERAGE_OUTPUT"),recursive=TRUE,showWarnings=FALSE)
env <- new.env(parent=globalenv())
sys.source(generated,envir=env)
sys.source(file.path(project,"tests/r/native_cases.R"),envir=env)
env$.mmm_write()
# Direct interpreter execution also covers the entrypoint's sys.nframe()==0 path.
inputs <- list.files(Sys.getenv("MMM_R_COVERAGE_INPUTS"),pattern="^predict-.*\\.json$",full.names=TRUE)
input <- inputs[which(vapply(inputs,function(path) length(jsonlite::fromJSON(path)$request$media_multiplier)==0L,logical(1)))[1L]]
stopifnot(length(input)==1L,!is.na(input))
Sys.setenv(MMM_R_BRANCH_JSON=child_json)
status <- system2(file.path(R.home("bin"),"Rscript.exe"),
                  c("--vanilla",shQuote(generated),shQuote(input),shQuote(file.path(root,"entrypoint-result.json"))),
                  stdout=file.path(root,"entrypoint.log"),stderr=file.path(root,"entrypoint-errors.log"))
stopifnot(status==0L)
parent <- jsonlite::fromJSON(parent_json,simplifyVector=FALSE)
child <- jsonlite::fromJSON(child_json,simplifyVector=FALSE)
counts <- lapply(names(definitions),function(id) {
  values <- unlist(parent[[id]])+unlist(child[[id]])
  list(id=id,kind=definitions[[id]]$kind,context=definitions[[id]]$context,
       expression=definitions[[id]]$expression,counts=as.list(values))
})
covered <- sum(vapply(counts,function(row) sum(unlist(row$counts)>0L),integer(1)))
total <- 2L*length(counts)
jsonlite::write_json(list(source_sha256=digest::digest(file=source_path,algo="sha256"),
                         covered=covered,total=total,percent=100*covered/total,branches=counts,
                         scope="All parsed first-party R if decisions and for body/exit branches, including direct entrypoint; no source exclusions"),
                    file.path(root,"coverage.json"),auto_unbox=TRUE,pretty=TRUE)
cat("R branches:",covered,"/",total,"=",100*covered/total,"%\n")
stopifnot(covered==total)
