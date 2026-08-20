def fitness_function(params, X, y):
    kf = KFold(n_splits=10, shuffle=True, random_state=42)
    rmse_scores = []
    for train_index, test_index in kf.split(X):
        X_train, X_test = X.iloc[train_index], X.iloc[test_index]
        y_train, y_test = y.iloc[train_index], y.iloc[test_index]

        model = lgb.LGBMRegressor(**params, verbose=-1, n_jobs=-1)
        model.fit(
            X_train,
            y_train,
            eval_X=X_test,
            eval_y=y_test,
            callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
        )
        pred = model.predict(X_test)
        rmse_scores.append(root_mean_squared_error(y_test, pred))
    return np.mean(rmse_scores)


def fitness_func_pygad(ga_instance, solution, solution_idx):
    params = {
        "num_leaves": int(solution[0]),
        "learning_rate": solution[1],
        "max_depth": int(solution[2]),
        "n_estimators": int(solution[3]),
        "min_child_samples": int(solution[4]),
        "subsample": solution[5],
        "colsample_bytree": solution[6],
        "min_child_weight": solution[7],
        "reg_alpha": solution[8],
        "reg_lambda": solution[9],
        "min_split_gain": solution[10],
        "bagging_freq": 1,
    }
    rmse = fitness_function(params, X, y)
    return -rmse


def run_for_ga(X, y):
    genetic_algorithm_instance = pygad.GA(
        num_generations=15,
        num_parents_mating=15,
        sol_per_pop=30,
        fitness_func=fitness_func_pygad,
        num_genes=11,
        mutation_percent_genes=[20, 5],
        gene_space=[
            {"low": 20, "high": 1000},
            {"low": 0.001, "high": 0.5},
            {"low": 3, "high": 15},
            {"low": 50, "high": 1000},
            {"low": 1, "high": 100},
            {"low": 0.5, "high": 1.0},
            {"low": 0.5, "high": 1.0},
            {"low": 1e-6, "high": 10.0},
            {"low": 0.0, "high": 10.0},
            {"low": 0.0, "high": 10.0},
            {"low": 0.0, "high": 1.0},
        ],
        gene_type=float,
        parent_selection_type="tournament",
        K_tournament=5,
        crossover_type="single_point",
        crossover_probability=0.9,
        mutation_type="adaptive",
        keep_elitism=2,
        on_generation=on_generation,
        parallel_processing={"num_cores": -1},
    )
    genetic_algorithm_instance.run()
    best_solution, best_solution_fitness, best_solution_idx = (
        genetic_algorithm_instance.best_solution()
    )
    return best_solution, genetic_algorithm_instance


def on_generation(ga_instance):
    best_fitness = ga_instance.best_solution()[1]
    print(f"Generation : {ga_instance.generations_completed}")
    print(f"RMSE : {-best_fitness:.4f}")
    print("--------------------------------------------------")


best_params_from_GA = {}
for col in comodity_cols:
    best_params_from_GA[col] = {}
    for h in horizontal_features:
        X = df_features[feature_cols_for(col)].dropna()
        y = df_features.loc[X.index, f"{col}_target_h{h}"]
        best_solution, ga_instance = run_for_ga(X, y)

        best_params_from_GA[col][h] = {
            "num_leaves": int(best_solution[0]),
            "learning_rate": best_solution[1],
            "max_depth": int(best_solution[2]),
            "n_estimators": int(best_solution[3]),
            "min_child_samples": int(best_solution[4]),
            "subsample": best_solution[5],
            "colsample_bytree": best_solution[6],
            "min_child_weight": best_solution[7],
            "reg_alpha": best_solution[8],
            "reg_lambda": best_solution[9],
            "min_split_gain": best_solution[10],
            "bagging_freq": 1,
        }
