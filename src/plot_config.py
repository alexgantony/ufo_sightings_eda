import seaborn as sns


def set_plot_theme():
    sns.set_theme(
        context="notebook",
        style="darkgrid",
        palette="ocean",
        color_codes=True,
        font_scale=1.1,
        rc={
            "figure.figsize": (10, 5),
            "axes.titlesize": 14,
            "axes.titleweight": "bold",
            "axes.labelsize": 12,
        },
    )
