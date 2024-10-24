# Backtrader Strategy with Stop Loss and Trailing Stop

This strategy implementation is built on the **Backtrader** library and offers a base class to facilitate the addition of custom trading strategies. It incorporates features such as stop loss, trailing stop, trade history logging, and performance tracking.

## Overview

The base strategy class `BaseStrategy` offers the following functionality:

- Buy signal execution with the ability to define the size of the order.
- Stop loss and trailing stop percentages for risk management.
- Record keeping of trade history, including profit/loss percentages for each trade.
- Cumulative capital tracking after each trade.
- Custom analyzers to track performance metrics such as the number of trades, maximum drawdown, and average return per trade.
- The strategy automatically saves trade history to a CSV file for later analysis.

You can extend this base strategy to build custom strategies by overriding the `next` method for buy/sell logic.

## How It Works

1. **Buy Signal**: Executes when a condition is met, allowing you to set a stop loss and trailing stop level based on the buy price.
2. **Sell Signal**: Can be triggered manually or through custom logic. The stop loss and trailing stop levels also ensure automatic trade exit in case of unfavorable price movements.
3. **Performance Analyzer**: Tracks the number of trades during the backtest.
4. **Result Saving**: All trade history is saved to a CSV file for external analysis.

## Code Breakdown

### Base Strategy Class

The `BaseStrategy` class serves as the foundation for building any custom strategy. It contains the logic for handling buy and sell signals, setting stop loss and trailing stop levels, and resetting trade parameters after execution.

```python
class BaseStrategy(bt.Strategy):
    params = (
        ('stop_loss_pct', 0.15),  # Default stop-loss percentage
        ('trailing_stop_pct', 0.1)  # Default trailing stop percentage
    )

    def __init__(self):
        self.last_buy_price = None
        self.stop_loss_price = None
        self.trailing_stop_price = None
        self.current_stocks = 0
        self.trade_history = []  # Store trade history
        self.cumulative_capital = []  # Store cumulative capital

    def next(self):
        self.cumulative_capital.append(self.broker.getvalue())  # Record capital

    def buy_signal(self, size):
        size = int(size)  # Ensure size is an integer
        if size > 0:
            self.buy(size=size)  # Execute buy order
            self.last_buy_price = self.data.close[0]
            self.stop_loss_price = self.last_buy_price * (1 - self.params.stop_loss_pct)
            self.trailing_stop_price = self.last_buy_price * (1 - self.params.trailing_stop_pct)
            self.current_stocks += size

    def sell_signal(self):
        exit_price = self.data.close[0]
        percentage_profit_or_loss = ((exit_price - self.last_buy_price) / self.last_buy_price) * 100

        self.trade_history.append({
            'action': 'sell',
            'buy_price': self.last_buy_price,
            'exit_price': exit_price,
            'size': -self.current_stocks,
            'percentage_profit_or_loss': percentage_profit_or_loss,
            'cumulative_capital': self.broker.getvalue()
        })
        self.sell(size=self.current_stocks)  # Execute sell order
        self.reset_trade()

    def reset_trade(self):
        self.last_buy_price = None
        self.stop_loss_price = None
        self.trailing_stop_price = None
        self.current_stocks = 0

    def stop(self):
        trade_history_df = pd.DataFrame(self.trade_history)
        trade_history_df.to_csv('trade_history_backtrader.csv', index=False)
        print("Trade history saved to CSV.")
```

### Performance Analyzer

This custom analyzer tracks the number of completed trades during the backtest.

```python
class PerformanceAnalyzer(bt.Analyzer):
    def __init__(self):
        self.total_trades = 0

    def notify_trade(self, trade):
        if trade.isclosed:
            self.total_trades += 1

    def get_analysis(self):
        return {'total_trades': self.total_trades}
```

### Data Loading

This function loads a `pandas` DataFrame into a Backtrader data feed.

```python
def load_data(data):
    return bt.feeds.PandasData(dataname=data, datetime='datetime', open='open', high='high', low='low', close='close', volume='volume')
```

### Running the Backtest

The `run_backtest` function executes the backtest by loading the data, setting up the strategy and analyzers, and then displaying the results.

```python
def run_backtest(data, strategy, stop_loss_pct=0.15, trailing_stop_pct=0.1, capital=10000, commission_rate=0.0015):
    cerebro = bt.Cerebro()
    cerebro.addstrategy(strategy, stop_loss_pct=stop_loss_pct, trailing_stop_pct=trailing_stop_pct)

    data_feed = load_data(data)
    cerebro.adddata(data_feed)

    cerebro.broker.setcash(capital)
    cerebro.broker.setcommission(commission=commission_rate)
    cerebro.addsizer(bt.sizers.FixedSize, stake=1)

    # Add analyzers
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(PerformanceAnalyzer, _name='performance')

    # Start backtest
    result = cerebro.run()

    # Fetch strategy result
    strat = result[0]
    total_return = strat.analyzers.returns.get_analysis()['rtot'] * 100
    market_return = (data['close'].iloc[-1] / data['close'].iloc[0] - 1) * 100
    num_trades = strat.analyzers.performance.get_analysis()['total_trades']
    max_drawdown = strat.analyzers.drawdown.get_analysis()['max']['drawdown']
    avg_trade_return = total_return / num_trades if num_trades > 0 else 0

    # Print result summary
    print(f"Total Return: {total_return:.2f}%")
    print(f"Market Return: {market_return:.2f}%")
    print(f"Number of Trades: {num_trades}")
    print(f"Max Drawdown: {max_drawdown:.2f}%")
    print(f"Average Return per Trade: {avg_trade_return:.2f}%")

    cerebro.plot()
```

### Example: EMA Crossover Strategy

You can define a custom strategy by extending the `BaseStrategy`. Below is an example of a simple **Exponential Moving Average (EMA) Crossover Strategy**:

```python
class EMACrossoverStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.short_ema = bt.indicators.EMA(self.data.close, period=20)
        self.long_ema = bt.indicators.EMA(self.data.close, period=50)

    def next(self):
        # Buy when short EMA crosses above long EMA
        if self.short_ema[0] > self.long_ema[0] and self.short_ema[-1] <= self.long_ema[-1]:
            size = self.broker.getvalue() / self.data.close[0]
            self.buy_signal(size)

        # Sell when short EMA crosses below long EMA
        elif self.short_ema[0] < self.long_ema[0] and self.current_stocks > 0:
            self.sell_signal()
```

### Running the EMA Crossover Strategy

Once you have defined the strategy, you can run it using the `run_backtest` function:

```python
if __name__ == '__main__':
    data = pd.read_csv('btcusdt_1h.csv', parse_dates=['datetime'])
    run_backtest(data, EMACrossoverStrategy)
```

## Customization

- Modify the parameters for stop loss and trailing stop percentages when adding the strategy using the `run_backtest` function.
- You can also change the logic in the `next` method of the strategy to define custom buy/sell conditions.

## Requirements

- `backtrader`
- `pandas`

You can install these packages using:

```bash
pip install backtrader pandas
```

## Conclusion

This base strategy setup provides a flexible framework for implementing and backtesting custom trading strategies using the Backtrader library. You can extend it with additional logic, indicators, and analyzers based on your requirements.
