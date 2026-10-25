# Local native Meta Robyn adapter. Host supplies private paths; no arbitrary R code input.
args <- commandArgs(trailingOnly=TRUE)
suppressPackageStartupMessages(library(jsonlite))
suppressPackageStartupMessages(library(Robyn))
payload <- fromJSON(args[1], simplifyVector=TRUE)
root <- dirname(args[2])
native <- file.path(root, "model.robyn.json")

robyn_split_indices <- function(n, train_size) {
  stopifnot(length(n)==1L, is.finite(n), n>=3L,
            length(train_size)==1L, is.finite(train_size), train_size>0, train_size<1)
  val_size <- (1-train_size)/2
  train_end <- floor(quantile(seq(n),train_size))
  validation_end <- train_end+floor(val_size*n)
  stopifnot(train_end>0L, validation_end>train_end, validation_end<n)
  list(train_end=unname(train_end), validation_end=unname(validation_end), test_end=n,
       train=seq_len(train_end), validation=seq.int(train_end+1L,validation_end),
       test=seq.int(validation_end+1L,n))
}

prepare_robyn_holdout <- function(df, target_column, date_column, warmup_periods,
                                train_size=0.6) {
  stopifnot(length(warmup_periods)==1L, is.finite(warmup_periods),
            warmup_periods>=0L, warmup_periods==as.integer(warmup_periods),
            all(is.finite(df[[target_column]])), all(df[[target_column]]>=0))
  split <- robyn_split_indices(nrow(df)-warmup_periods,train_size)
  train_rows <- split$train+warmup_periods
  test_rows <- split$test+warmup_periods
  placeholder <- mean(df[[target_column]][train_rows])
  stopifnot(is.finite(placeholder))
  model_df <- df
  model_df[[target_column]][test_rows] <- placeholder
  list(rows=model_df,policy=list(
    policy="outer_test_target_replaced_with_train_mean_before_native_inputs",
    placeholder=placeholder,train_rows=length(train_rows),
    validation_rows=length(split$validation),test_rows=length(test_rows),
    warmup_rows=warmup_periods,test_dates=as.character(df[[date_column]][test_rows]),
    target_outer_test_used_in_native_search=FALSE,
    validation_target_used_for_hyperparameter_selection=TRUE,
    media_and_control_holdout_values="known_conditional_historical_scenario",
    native_test_diagnostics="placeholder_target_not_observed_use_adapter_metrics"))
}

partition_summary <- function(predictions, indices) {
  test <- predictions[indices,,drop=FALSE]
  observed <- test$dep_var
  predicted <- test$depVarHat
  variance <- sum((observed-mean(observed))^2)
  denominator <- sum(abs(observed))
  list(dates=as.character(test$ds), mean=predicted, interval_type="not_available_point_prediction",
       metrics=list(mae=mean(abs(observed-predicted)),
                    wape_percent=if(denominator>0)100*sum(abs(observed-predicted))/denominator else NULL,
                    r2=if(variance>0)1-sum((observed-predicted)^2)/variance else NULL))
}

prediction_summary <- function(output, selected, observed_data=NULL,
                               target_column=NULL, date_column=NULL) {
  predictions <- output$xDecompVecCollect
  predictions <- predictions[predictions$solID == selected, , drop=FALSE]
  predictions <- predictions[order(predictions$ds), , drop=FALSE]
  stopifnot(nrow(predictions)>0L, all(is.finite(predictions$depVarHat)))
  if(!is.null(observed_data)) {
    indices <- match(as.character(predictions$ds),as.character(observed_data[[date_column]]))
    stopifnot(!anyNA(indices))
    predictions$dep_var <- observed_data[[target_column]][indices]
  }
  selected_hyper <- output$resultHypParam[output$resultHypParam$solID==selected,,drop=FALSE]
  stopifnot(nrow(selected_hyper)==1L)
  train_size <- selected_hyper$train_size[[1L]]
  split <- robyn_split_indices(nrow(predictions),train_size)
  summary <- partition_summary(predictions,split$test)
  summary$scope <- "native_ts_validation_test_partition"
  summary$temporal_split <- list(train_fraction=train_size,train_end=split$train_end,
    validation_end=split$validation_end,test_end=split$test_end,
    index_convention="one_based_inclusive_endpoints_in_effective_model_window",
    train_dates=as.character(predictions$ds[split$train]),
    validation_dates=as.character(predictions$ds[split$validation]),
    test_dates=as.character(predictions$ds[split$test]))
  summary$train <- partition_summary(predictions,split$train)
  summary$validation <- partition_summary(predictions,split$validation)
  summary
}

if(payload$operation == "train") {
  req <- payload$request
  target_type <- payload$dataset$target_type
  if(is.null(target_type)) target_type <- "unspecified"
  if(identical(target_type,"unspecified") && isTRUE(payload$dataset$synthetic) &&
     identical(payload$dataset$source,"built-in-demo-v1") && identical(req$target_column,"revenue")) {
    target_type <- "revenue"
  }
  stopifnot(target_type %in% c("revenue","non_revenue"))
  dep_var_type <- if(identical(target_type,"revenue")) "revenue" else "conversion"
  df <- payload$dataset$rows
  observed_data <- df
  prepared <- prepare_robyn_holdout(df,req$target_column,req$date_column,req$warmup_periods)
  df <- prepared$rows
  media <- as.character(req$media_columns)
  controls <- as.character(req$control_columns)
  df[[req$date_column]] <- as.Date(df[[req$date_column]])
  days <- as.numeric(df[[req$date_column]]-min(df[[req$date_column]]))
  df$trend_years <- days/365.25
  df$sin_year <- sin(2*pi*days/365.25)
  df$cos_year <- cos(2*pi*days/365.25)
  controls <- c(controls,"trend_years","sin_year","cos_year")
  hyper <- list(train_size=0.6)
  for(channel in media) {
    hyper[[paste0(channel,"_alphas")]] <- c(0.5,3)
    hyper[[paste0(channel,"_gammas")]] <- c(0.1,0.9)
    hyper[[paste0(channel,"_thetas")]] <- c(0,0.8)
  }
  input <- robyn_inputs(dt_input=df,date_var=req$date_column,dep_var=req$target_column,
    dep_var_type=dep_var_type,paid_media_spends=media,paid_media_vars=media,
    paid_media_signs=rep("positive",length(media)),context_vars=controls,
    context_signs=rep("default",length(controls)),prophet_vars=NULL,prophet_country=NULL,
    dt_holidays=NULL,adstock="geometric",hyperparameters=hyper,
    window_start=as.character(df[[req$date_column]][req$warmup_periods+1L]),
    window_end=as.character(tail(df[[req$date_column]],1)))
  models <- robyn_run(InputCollect=input,trials=1L,iterations=max(200L,as.integer(req$draws)*4L),
    cores=1L,ts_validation=TRUE,seed=as.integer(req$seed),nevergrad_algo="TwoPointsDE",
    intercept_sign="unconstrained",outputs=FALSE,quiet=FALSE)
  output <- robyn_outputs(InputCollect=input,OutputModels=models,pareto_fronts=1,
    min_candidates=1,clusters=FALSE,plot_pareto=FALSE,csv_out=NULL,export=FALSE,quiet=TRUE)
  candidates <- output$resultHypParam
  candidates <- candidates[is.finite(candidates$nrmse_val),,drop=FALSE]
  stopifnot(nrow(candidates)>0)
  candidates <- candidates[order(candidates$nrmse_val,candidates$solID),,drop=FALSE]
  selected <- as.character(candidates$solID[1])
  before <- prediction_summary(output,selected,observed_data,req$target_column,req$date_column)
  exported <- robyn_write(InputCollect=input,OutputCollect=output,select_model=selected,
                         add_data=TRUE,export=FALSE,quiet=TRUE)
  write_json(exported,native,auto_unbox=TRUE,digits=16,null="null")
  restored <- robyn_recreate(native,quiet=TRUE,cores=1L,clusters=FALSE,plot_pareto=FALSE,csv_out=NULL)
  after <- prediction_summary(restored$OutputCollect,selected,observed_data,
                              req$target_column,req$date_column)
  stopifnot(isTRUE(all.equal(before$mean,after$mean,tolerance=1e-5)))
  result <- list(backend="meta_robyn",backend_version=as.character(packageVersion("Robyn")),
    r_version=as.character(getRversion()),restore_verified=TRUE,selected_id=selected,test=before,
    holdout_policy=prepared$policy,
    effective_configuration=list(model_type="regularized_ridge_nevergrad",
      target_type=target_type,dep_var_type=dep_var_type,adstock="geometric",
      hyperparameter_search=hyper,selected_hyperparameters=candidates[1,,drop=FALSE],
      paid_media_signs=rep("positive",length(media)),media_input="spend_proxy",
      priors=NULL,priors_status="not_applicable_non_bayesian_model",
      interval_type="not_available_point_prediction"),
    temporal_split=before$temporal_split,
    diagnostics=list(trials=1L,iterations=max(200L,as.integer(req$draws)*4L),
                     selection="validation_nrmse",convergence_certified=FALSE),
    warnings=c("Functional reduced search, not recommended production search volume",
      "Native temporal validation has its own rounding and warmup window",
      "Adapter isolates outer test targets with train-only placeholders; not default Robyn behavior",
      "Native test diagnostics use placeholders; adapter test metrics use original observations",
      "Spend used as exposure proxy; no demonstrated causal attribution"))
} else {
  stored <- payload$model
  req <- stored$request
  writeBin(base64_dec(stored$native_base64),native)
  restored <- robyn_recreate(native,quiet=TRUE,cores=1L,clusters=FALSE,plot_pareto=FALSE,csv_out=NULL)
  selected <- stored$selected_id
  multipliers <- payload$request$media_multiplier
  if(length(multipliers)>0L) {
    responses <- list()
    for(channel in names(multipliers)) {
      stopifnot(channel %in% stored$request$media_columns)
      original <- restored$InputCollect$dt_input[[channel]]
      response <- robyn_response(InputCollect=restored$InputCollect,OutputCollect=restored$OutputCollect,
        select_model=selected,metric_name=channel,metric_value=mean(original)*multipliers[[channel]],
        date_range="all",quiet=TRUE)
      responses[[channel]] <- list(response_total=response$response_total,
                                  response_carryover=response$response_carryover)
    }
    result <- list(backend="meta_robyn",model_id=stored$model_id,scope="native_channel_response",
                   responses=responses,exploratory=TRUE,
                   warnings="Native channel response is not a full future revenue forecast")
  } else {
    result <- list(backend="meta_robyn",model_id=stored$model_id,scope="historical_restored_prediction",
      prediction=prediction_summary(restored$OutputCollect,selected,stored$dataset$rows,
        req$target_column,req$date_column),exploratory=TRUE,
      warnings="Historical prediction, not causal attribution or future forecast")
  }
}
write_json(result,args[2],auto_unbox=TRUE,digits=16,null="null",na="null")
