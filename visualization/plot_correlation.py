# projectAlgo/visualization/plot_correlation.py
# Interactive Plotly heatmap for a correlation matrix.

import pandas as pd
import plotly.graph_objects as go


def plot_correlation_heatmap(corr: pd.DataFrame, title: str = 'Correlation Matrix',
                              open_browser: bool = True) -> go.Figure:
    """
    Renders an annotated, interactive correlation heatmap.

    Color scale: red (−1) → white (0) → green (+1).
    Each cell is annotated with the rounded correlation value.

    Args:
        corr:         Square correlation DataFrame (output of calculate_correlation_matrix).
        title:        Plot title.
        open_browser: If True, opens the figure in the default browser.

    Returns:
        The Plotly Figure object.
    """
    if corr.empty:
        print("Correlation matrix is empty — nothing to plot.")
        return go.Figure()

    tickers = corr.columns.tolist()
    z = corr.values.tolist()

    # Annotation text: value rounded to 2 dp, blank on diagonal
    annotations = []
    for i, row_ticker in enumerate(tickers):
        for j, col_ticker in enumerate(tickers):
            val = corr.iloc[i, j]
            text = '' if i == j else f'{val:.2f}'
            annotations.append(dict(
                x=col_ticker, y=row_ticker,
                text=text, showarrow=False,
                font=dict(color='black' if abs(val) < 0.7 else 'white', size=12),
            ))

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=tickers,
        y=tickers,
        colorscale=[
            [0.0,  'rgb(215,  25,  28)'],
            [0.25, 'rgb(253, 174,  97)'],
            [0.5,  'rgb(255, 255, 191)'],
            [0.75, 'rgb(166, 217, 106)'],
            [1.0,  'rgb( 26, 150,  65)'],
        ],
        zmin=-1, zmax=1,
        colorbar=dict(title='ρ', tickvals=[-1, -0.5, 0, 0.5, 1]),
        hovertemplate='%{y} / %{x}<br>ρ = %{z:.4f}<extra></extra>',
    ))

    fig.update_layout(
        title=dict(text=title, x=0.5),
        annotations=annotations,
        xaxis=dict(side='bottom', tickangle=-45),
        yaxis=dict(autorange='reversed'),
        width=max(500, 80 * len(tickers)),
        height=max(450, 75 * len(tickers)),
        margin=dict(l=80, r=40, t=80, b=100),
        template='plotly_white',
    )

    if open_browser:
        fig.show()

    return fig
