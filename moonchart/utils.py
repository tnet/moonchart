# Copyright 2019 QuantRocket LLC - All Rights Reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pandas as pd
import numpy as np

def get_zscores(returns):
    """
    Returns the Z-scores of the input returns.

    Parameters
    ----------
    returns : Series or DataFrame, required
        Series or DataFrame of returns

    Returns
    -------
    Series or DataFrame
    """
    # Ignore 0 returns in calculating z score
    nonzero_returns = returns.where(returns != 0)
    z_scores = (nonzero_returns - nonzero_returns.mean())/nonzero_returns.std()
    return z_scores

def trim_outliers(returns, z_score):
    """
    Zeroes out observations that are too many standard deviations from the
    mean.

    Parameters
    ----------
    returns : Series or DataFrame, required
        Series or DataFrame of returns

    z_score : int or float, required
        maximum standard deviation values are allowed to be from the mean

    Returns
    -------
    Series or DataFrame
    """
    z_scores = get_zscores(returns)
    return returns.where(z_scores.abs() <= z_score, 0)

def with_baseline(data, value=1):
    """
    Prepends a date-indexed Series or DataFrame with an initial row that is
    one period earlier than the first row and has the specified value.

    The typical use case is for generating plots: without a baseline row, a cumulative
    returns plot won't start from 1 if the first day's return is nonzero.

    Parameters
    ----------
    data : Series or DataFrame, required
        Series or DataFrame (for example, of returns)

    value : required
        value to insert in the baseline row

    Returns
    -------
    Series or DataFrame

    Examples
    --------
    Typical usage:

    >>> with_baseline(cum_returns).plot()

    Under the hood:

    >>> cum_returns.head()
        2019-01-02   1.01
        2019-01-03  0.995
    >>> with_baseline(cum_returns)
        2019-01-01      1
        2019-01-02   1.01
        2019-01-03  0.995
    """
    period_length = data.index[1] - data.index[0]
    prior_period = data.index[0] - period_length
    if isinstance(data, pd.DataFrame):
        baseline_row = pd.DataFrame(value, index=[prior_period], columns=data.columns)
    else:
        baseline_row = pd.Series(value, index=[prior_period], name=data.name)
    try:
        data_with_baseline = pd.concat((baseline_row, data), sort=False)
    except TypeError:
        # sort was introduced in pandas 0.23
        data_with_baseline = pd.concat((baseline_row, data))
    return data_with_baseline

def get_sharpe(returns, riskfree=0):
    """
    Returns the Sharpe ratio of the returns.

    Parameters
    ----------
    returns : Series or DataFrame, required
        a Series or DataFrame of returns

    riskfree : float, optional
        the risk-free rate (default 0)

    Returns
    -------
    float or Series of floats
    """
    mean = (returns - riskfree).mean()
    if isinstance(mean, float) and mean == 0:
        return 0
    std = (returns - riskfree).std()
    # Returns are assumed to represent daily returns, so annualize the Sharpe ratio
    return mean/std * np.sqrt(252)

def get_rolling_sharpe(returns, window, riskfree=0):
    """
    Computes rolling Sharpe ratios for the returns.

    Parameters
    ----------
    returns : Series or DataFrame, required
        a Series or DataFrame of returns

    window : int, required
        rolling window length

    riskfree : float, optional
        the risk-free rate (default 0)

    Returns
    -------
    Series or DataFrame
    """
    rolling_returns = returns.fillna(0).rolling(window, min_periods=window)
    try:
        return rolling_returns.apply(get_sharpe, raw=True, kwargs=dict(riskfree=riskfree))
    except TypeError as e:
        # handle pandas<0.23
        if "apply() got an unexpected keyword argument 'raw'" in repr(e):
            return rolling_returns.apply(get_sharpe, kwargs=dict(riskfree=riskfree))
        else:
            raise

def get_cum_returns(returns, compound=True):
    """
    Computes the cumulative returns of the provided returns.

    Parameters
    ----------
    returns : Series or DataFrame, required
        a Series or DataFrame of returns

    compound : bool
        True for compounded (geometric) returns, False for arithmetic
        returns (default True)

    Returns
    -------
    Series or DataFrame
    """
    if compound:
        cum_returns = (1 + returns).cumprod()
    else:
        cum_returns = returns.cumsum() + 1

    cum_returns.index.name = "Date"
    return cum_returns

def get_cagr(cum_returns, compound=True):
    """
    Computes the CAGR from the cumulative returns.

    Parameters
    ----------
    cum_returns : Series or DataFrame, required
        a Series or DataFrame of cumulative returns

    compound : bool
        compute compound annual growth rate if True, otherwise
        compute average annual return (default True)

    Returns
    -------
    float or Series of floats
    """
    # For DataFrames, apply this function to each Series.
    if isinstance(cum_returns, pd.DataFrame):
        return cum_returns.apply(get_cagr, axis=0)

    # Ignore nulls when compting CAGR
    cum_returns = cum_returns[cum_returns.notnull()]

    if cum_returns.empty:
        return 0

    # Compute the CAGR of the Series
    min_date = cum_returns.index.min()
    max_date = cum_returns.index.max()
    years = ((max_date - min_date).days or 1)/365.0
    ending_value = cum_returns.iloc[-1]
    # Since we are computing CAGR on cumulative returns, the beginning
    # value is always 1.
    beginning_value = 1
    if compound:
        cagr = (ending_value/beginning_value)**(1/years) - 1
    else:
        # Compound annual growth rate doesn't apply to arithmetic
        # returns, so just divide the cum_returns by the number of years
        # to get the annual return
        cagr = (ending_value/beginning_value - 1)/years

    return cagr

def get_drawdowns(cum_returns):
    """
    Computes the drawdowns of the cumulative returns.

    Parameters
    ----------
    cum_returns : Series or DataFrame, required
        a Series or DataFrame of cumulative returns

    Returns
    -------
    Series or DataFrame
    """
    cum_returns = cum_returns[cum_returns.notnull()]
    highwater_marks = cum_returns.expanding().max()
    drawdowns = cum_returns/highwater_marks - 1
    return drawdowns

def get_top_movers(returns, n=10):
    """
    Returns the biggest gainers and losers in the returns.

    Parameters
    ----------
    returns : Series or DataFrame, required
        a Series or DataFrame of returns

    n : int, optional
        the number of biggest gainers and losers to return (default 10)

    Returns
    -------
    Series or DataFrame
    """

    if isinstance(returns, pd.DataFrame):
        returns = returns.stack()

    returns = returns.sort_values()

    try:
        top_movers = pd.concat((returns.head(n), returns.tail(n)), sort=True)
    except TypeError:
        # sort was introduced in pandas 0.23
        top_movers = pd.concat((returns.head(n), returns.tail(n)))

    return top_movers
