# Executed by covr in the environment containing the real adapter functions.
expect_error <- function(expr) {
  failed <- tryCatch({force(expr);FALSE}, error=function(e) TRUE)
  stopifnot(failed)
}
split <- robyn_split_indices(10,0.6)
stopifnot(identical(split$train,1:6),identical(split$validation,7:8),identical(split$test,9:10))
expect_error(robyn_split_indices(2,0.6))
expect_error(robyn_split_indices(10,0))
expect_error(robyn_split_indices(10,0.99))
df <- data.frame(date=as.character(as.Date("2026-01-05")+7*(0:51)),revenue=100:151)
prepared <- prepare_robyn_holdout(df,"revenue","date",8)
stopifnot(all(tail(prepared$rows$revenue,10)==120.5),identical(df$revenue,100:151))
expect_error(prepare_robyn_holdout(df,"revenue","date",-1))
fake <- data.frame(ds=as.character(as.Date("2026-01-05")+7*(0:9)),dep_var=1:10,depVarHat=2:11,solID="chosen")
output <- list(xDecompVecCollect=fake,resultHypParam=data.frame(solID="chosen",train_size=0.6))
summary <- prediction_summary(output,"chosen")
stopifnot(summary$metrics$mae==1,abs(summary$metrics$wape_percent-200/19)<1e-12)
observed <- data.frame(date=fake$ds,target=2:11)
summary <- prediction_summary(output,"chosen",observed,"target","date")
stopifnot(summary$metrics$mae==0)
expect_error(prediction_summary(output,"missing"))
observed$date[1] <- "2025-01-01"
expect_error(prediction_summary(output,"chosen",observed,"target","date"))
zeros <- partition_summary(data.frame(ds=1:5,dep_var=rep(0,5),depVarHat=rep(1,5)),1:5)
stopifnot(is.null(zeros$metrics$r2),is.null(zeros$metrics$wape_percent))
expect_error(main(character()))

inputs <- list.files(Sys.getenv("MMM_R_COVERAGE_INPUTS"),pattern="\\.json$",full.names=TRUE)
stopifnot(length(inputs)>=3L)
cases <- list()
for(input in inputs) {
  payload <- jsonlite::fromJSON(input,simplifyVector=FALSE)
  kind <- if(payload$operation=="train") "train" else if(length(payload$request$media_multiplier)>0L) "scenario" else "predict"
  if(is.null(cases[[kind]])) cases[[kind]] <- input
}
stopifnot(all(c("train","predict","scenario") %in% names(cases)))
legacy <- jsonlite::fromJSON(cases$train,simplifyVector=FALSE)
legacy$dataset$target_type <- NULL
legacy$dataset$source <- "built-in-demo-v1"
legacy_path <- file.path(Sys.getenv("MMM_R_COVERAGE_OUTPUT"),"legacy-input.json")
jsonlite::write_json(legacy,legacy_path,auto_unbox=TRUE,null="null",digits=16)
cases$legacy <- legacy_path
conversion <- legacy
conversion$dataset$target_type <- "non_revenue"
conversion$dataset$units$revenue <- "count"
conversion_path <- file.path(Sys.getenv("MMM_R_COVERAGE_OUTPUT"),"conversion-input.json")
jsonlite::write_json(conversion,conversion_path,auto_unbox=TRUE,null="null",digits=16)
cases$conversion <- conversion_path
for(kind in names(cases)) {
  folder <- file.path(Sys.getenv("MMM_R_COVERAGE_OUTPUT"),kind)
  dir.create(folder,recursive=TRUE,showWarnings=FALSE)
  destination <- file.path(folder,"result.json")
  main(c(cases[[kind]],destination))
  actual <- jsonlite::fromJSON(destination)
  stopifnot(actual$backend=="meta_robyn")
  if(kind=="train") stopifnot(isTRUE(actual$restore_verified),all(is.finite(actual$test$mean)))
  if(kind=="predict") stopifnot(actual$scope=="historical_restored_prediction",all(is.finite(actual$prediction$mean)))
  if(kind=="scenario") {
    stopifnot(actual$scope=="native_channel_response",all(is.finite(actual$responses$spend_search$response_total)),is.finite(actual$responses$spend_search$scenario_mean_response))
    baseline <- jsonlite::fromJSON(cases[[kind]],simplifyVector=FALSE)
    baseline$request$media_multiplier$spend_search <- 1.0
    baseline_input <- file.path(folder,"baseline-input.json")
    baseline_output <- file.path(folder,"baseline-result.json")
    jsonlite::write_json(baseline,baseline_input,auto_unbox=TRUE,null="null",digits=16)
    main(c(baseline_input,baseline_output))
    reference <- jsonlite::fromJSON(baseline_output)
    factor <- actual$responses$spend_search$requested_multiplier
    stopifnot(isTRUE(all.equal(actual$responses$spend_search$scenario_mean_spend,
                              reference$responses$spend_search$scenario_mean_spend*factor,tolerance=1e-8)))
  }
  if(kind=="legacy") stopifnot(actual$effective_configuration$target_type=="revenue",isTRUE(actual$restore_verified))
  if(kind=="conversion") stopifnot(actual$effective_configuration$dep_var_type=="conversion",isTRUE(actual$restore_verified))
}
