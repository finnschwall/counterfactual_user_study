import json

import pandas as pd
import numpy as np
import logging
import os
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import train_test_split
import joblib
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.ensemble import RandomForestClassifier
from plugins.api import *
from numpy.polynomial import Polynomial
from CFApi import CFGenerator
standard_config = {"data_path": "/home/finn/Fraunhofer/working_dir/plugins/raw_data/train.xls",
                   "target": "price_range", "delimiter": ","}
logger = logging.getLogger("DataPlugin")


@plugin_init(namespace="BasicML", name="data", plugin_type=PluginType.DATA,
             venv_path="/home/finn/.pyenv/versions/counterfactuals/bin/python3",
             is_local=False, config=standard_config, config_is_server_managed=True)
def data(ctx, config, meta_config):
    dataset = pd.read_csv("../plugins/raw_data/data.csv")
    target = dataset["F"]
    datasetX = dataset.drop("F", axis=1)
    x_train, x_test, y_train, y_test = train_test_split(datasetX,
                                                        target,
                                                        test_size=0.2,
                                                        random_state=0)

    numerical = list(x_train.select_dtypes(include=[np.number]))
    categorical = x_train.columns.difference(numerical)

    numeric_transformer = Pipeline(steps=[
        ('scaler', StandardScaler())])

    categorical_transformer = Pipeline(steps=[
        ('onehot', OneHotEncoder(handle_unknown='ignore'))])

    transformations = ColumnTransformer(
        transformers=[
            ('num', numeric_transformer, numerical),
            ('cat', categorical_transformer, categorical)])
    clf = Pipeline(steps=[('preprocessor', transformations),
                          ('classifier', RandomForestClassifier())])
    model = clf.fit(x_train, y_train)
    ctx.data = pd.read_csv(config["data_path"], sep=config["delimiter"])
    ctx.max_row_index = len(ctx.data)
    ctx.model = model

    ctx.cf_generator = CFGenerator(dataset, "F", model)
    ctx.basefile = logger.parent.handlers[1].baseFilename

    terms = [
        1.4999999999972982e+001,
        -1.4277579359791918e+001,
        6.8005423224871588e+000,
        -1.7613062148029233e+000,
        2.4917658692336944e-001,
        -1.8019179862574442e-002,
        5.1917989317582284e-004
    ]
    ctx.p = Polynomial(terms)
    ctx.selected_row = -1
    if not os.path.exists("generator_options.json"):
        with open("generator_options.json", "w") as f:
            json.dump(ctx.cf_generator.generator_options, f)
    if not os.path.exists("run_options.json"):
        with open("run_options.json", "w") as f:
            json.dump(ctx.cf_generator.general_run_arguments, f)

@data.plugin_method()
def start_session(api, path):
    logger.parent.handlers[1].close()
    logger.parent.handlers[1].baseFilename = path
    logger.info("Session started")

@data.plugin_method()
def end_session(api):
    logger.info("Session ended")
    logger.parent.handlers[1].close()
    logger.parent.handlers[1].baseFilename = data.ctx.basefile

@data.plugin_method()
def get_len_dataset(api):
    return data.ctx.max_row_index


@data.plugin_method()
def calculate_cfs(api, index=-1, feature_weights=None):

    logger.info(f"Requested CF for index: \"{index}\" with weights: \"{feature_weights}\"")
    # index = data.ctx.selected_row
    if index==-1:
        api.display_html("<h2>No data selected to generate counterfactuals for!</h2>")
        return
    instance = data.ctx.data.iloc[index:index + 1]
    outcome = data.ctx.model.predict(instance)

    if feature_weights is None:
        for i in data.ctx.cf_generator.metadata.var_metadata:
            if i !="F":
                data.ctx.cf_generator.metadata.var_metadata[i].feature_weight = 1
    else:
        for i in feature_weights:
            if feature_weights[i] == "-5":
                data.ctx.cf_generator.metadata.var_metadata[i].is_excluded = True
            else:
                data.ctx.cf_generator.metadata.var_metadata[i].is_excluded = False

        for i in data.ctx.cf_generator.metadata.var_metadata:
            if i !="F":
                data.ctx.cf_generator.metadata.var_metadata[i].feature_weight = data.ctx.p(float(feature_weights[i])+5)

    with open("run_options.json", "r") as f:
        data.ctx.cf_generator.general_run_arguments = json.load(f)
    with open("generator_options.json", "r") as f:
        data.ctx.cf_generator.generator_options = json.load(f)
    final_df = data.ctx.cf_generator.generate_counterfactuals(instance, [0.5, 1] if outcome[0] == 0 else [0, 0.499],
                                                              multithreaded=False)
    if isinstance(final_df, str):
        api.display_html(f"<h1>{final_df}</h1>")
        logger.info(f"No counterfactuals found. Reason: \"{final_df}\"")
        return
    html = final_df.to_html(classes=["table"], justify="left", index=False)
    html = html.replace("<tbody>\n    <tr>", '<tbody>\n    <tr class="table-active">')
    if data.ctx.cf_generator.num_cfs_found < 10:
        logger.info(f"Only {data.ctx.cf_generator.num_cfs_found} counterfactuals found")
        api.display_html("<h1>Nicht alle geforderten counterfactuals konnten gefunden werden.</h1>"+html)
    else:
        logger.info("All counterfactuals found")
        api.display_html(html)

@data.plugin_method()
@argument('index', type=int)
def get_data_point(api, index):
    logger.info(f"User requested datapoint {index}")
    if index > data.ctx.max_row_index:
        raise IndexError(f"Max row is {data.ctx.max_row_index}")
    if data.config["target"] in data.ctx.data:
        row = data.ctx.data.iloc[index:index + 1].drop(columns=[data.config["target"]])
    else:
        row = data.ctx.data.iloc[index:index + 1]
    outcome = data.ctx.model.predict(row)
    row["F"] = outcome

    # api.save("selected_row", index)
    data.ctx.selected_row = index
    row.index = [row.index[0]+1]
    api.display_html("<h1>Ausgewählter Datenpunkt:</h1>"+row.to_html(classes=["table"], justify="left"))
