# Local native Meta Robyn adapter. Host supplies private paths; no arbitrary R code input.
args <- commandArgs(trailingOnly=TRUE)
suppressPackageStartupMessages(library(jsonlite))
suppressPackageStartupMessages(library(Robyn))
payload <- fromJSON(args[1], simplifyVector=TRUE)
root <- dirname(args[2])
native <- file.path(root, "model.robyn.json")

prediction_summary <- function(output, selected) {
  predictions <- output$xDecompVecCollect
  predictions <- predictions[predictions$solID == selected, , drop=FALSE]
  predictions <- predictions[order(predictions$ds), , drop=FALSE]
  stopifnot(nrow(predictions)>0L, all(is.finite(predictions$depVarHat)))
  ntest <- ceiling(nrow(predictions)*0.2)
  test <- tail(predictions, ntest)
  observed <- test$dep_var
  predicted <- test$depVarHat
  variance <- sum((observed-mean(observed))^2)
  list(dates=as.character(test$ds), mean=predicted,
       metrics=list(mae=mean(abs(observed-predicted)),
                    wape_percent=100*sum(abs(observed-predicted))/sum(abs(observed)),
                    r2=if(variance>0)1-sum((observed-predicted)^2)/variance else NULL),
       scope="native_ts_validation_tail_20_percent")
}

if(payload$operation == "train") {
  req <- payload$request
  df <- payload$dataset$rows
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
    dep_var_type="revenue",paid_media_spends=media,paid_media_vars=media,
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
  before <- prediction_summary(output,selected)
  exported <- robyn_write(InputCollect=input,OutputCollect=output,select_model=selected,
                         add_data=TRUE,export=FALSE,quiet=TRUE)
  write_json(exported,native,auto_unbox=TRUE,digits=16,null="null")
  restored <- robyn_recreate(native,quiet=TRUE,cores=1L,clusters=FALSE,plot_pareto=FALSE,csv_out=NULL)
  after <- prediction_summary(restored$OutputCollect,selected)
  stopifnot(isTRUE(all.equal(before$mean,after$mean,tolerance=1e-5)))
  result <- list(backend="meta_robyn",backend_version=as.character(packageVersion("Robyn")),
    r_version=as.character(getRversion()),restore_verified=TRUE,selected_id=selected,test=before,
    diagnostics=list(trials=1L,iterations=max(200L,as.integer(req$draws)*4L),
                     selection="validation_nrmse",convergence_certified=FALSE),
    warnings=c("Functional reduced search, not recommended production search volume",
      "Native temporal validation has its own rounding and warmup window",
      "Spend used as exposure proxy; no demonstrated causal attribution"))
} else {
  stored <- payload$model
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
      prediction=prediction_summary(restored$OutputCollect,selected),exploratory=TRUE,
      warnings="Historical prediction, not causal attribution or future forecast")
  }
}
write_json(result,args[2],auto_unbox=TRUE,digits=16,null="null",na="null")
