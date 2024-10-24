import backtrader as bt
import pandas as pd

# Custom strategy class for EMA Crossover with stop-loss and trailing stop
class EMACrossoverStrategy(bt.Strategy):
    params = (
        ('short_ema_period', 20),  # Short EMA period
        ('long_ema_period', 50),    # Long EMA period
        ('stop_loss_pct', 0.1),     # 10% stop-loss
        ('trailing_stop_pct', 0.1)   # 10% trailing stop
    )

    def __init__(self):
        self.short_ema = bt.indicators.ExponentialMovingAverage(self.data.close, period=self.params.short_ema_period)
        self.long_ema = bt.indicators.ExponentialMovingAverage(self.data.close, period=self.params.long_ema_period)
        self.last_buy_price = None
        self.stop_loss_price = None
        self.trailing_stop_price = None
        self.current_stocks = 0
        self.trade_history = []  # List to store trade history
        self.cumulative_capital = []  # List to store cumulative capital history
    
    def next(self):
        # Record current capital
        self.cumulative_capital.append(self.broker.getvalue())

        # Buy signal: Short EMA crosses above Long EMA
        if self.short_ema[0] > self.long_ema[0] and self.short_ema[-1] <= self.long_ema[-1]:
            size = self.broker.getvalue() / self.data.close[0]
            self.buy(size=size)  # Execute buy order
            self.last_buy_price = self.data.close[0]
            self.stop_loss_price = self.last_buy_price * (1 - self.params.stop_loss_pct)  # Set stop-loss
            self.trailing_stop_price = self.last_buy_price * (1 - self.params.trailing_stop_pct)  # Set trailing stop
            self.current_stocks += size
            print(f"BUY executed at {self.data.close[0]}")
            self.trade_history.append({
                'action': 'buy',
                'entry_price': self.last_buy_price,  # Track entry price
                'size': size,  # Store the size (positive)
                "profit_or_loss": None,
                'cumulative_capital': self.broker.getvalue()  # Store cumulative capital at entry
            })

        # Sell signal: Short EMA crosses qqbelow Long EMA
        elif self.short_ema[0] < self.long_ema[0] and self.short_ema[-1] >= self.long_ema[-1] and self.current_stocks > 0:
            exit_price = self.data.close[0]
            self.sell(size=self.current_stocks)  # Execute sell order
            profit_or_loss = exit_price - self.last_buy_price
            self.trade_history.append({
                "action": "sell",
                'exit_price': exit_price,  # Track exit price
                'size': -self.current_stocks,  # Store the size (negative)
                'profit_or_loss': profit_or_loss,  # Store profit or loss
                'cumulative_capital': self.broker.getvalue()  # Store cumulative capital at exit
            })
            print(f"SELL executed at {exit_price}")
            self.reset_trade()

        # Check for stop-loss or trailing stop to trigger a sell
        if self.current_stocks > 0 and self.last_buy_price is not None:
            # Stop-loss condition
            if self.data.close[0] <= self.stop_loss_price:
                print(f"Stop-loss triggered at {self.data.close[0]}")
                self.trigger_sell("sell SL")
            # Trailing stop condition
            elif self.data.close[0] <= self.trailing_stop_price:
                print(f"Trailing stop triggered at {self.data.close[0]}")
                self.trigger_sell("sell trailing SL")

            # Adjust trailing stop if the price increases after a buy
            elif self.data.close[0] > self.last_buy_price:
                self.trailing_stop_price = max(self.trailing_stop_price, self.data.close[0] * (1 - self.params.trailing_stop_pct))

    def trigger_sell(self, action):
        exit_price = self.data.close[0]
        self.sell(size=self.current_stocks)  # Execute sell order
        profit_or_loss = exit_price - self.last_buy_price
        self.trade_history.append({
            "action": action,
            'exit_price': exit_price,  # Track exit price
            'size': -self.current_stocks,  # Store the size (negative)
            'profit_or_loss': profit_or_loss,  # Store profit or loss
            'cumulative_capital': self.broker.getvalue()  # Store cumulative capital at exit
        })
        self.reset_trade()

    def reset_trade(self):
        self.last_buy_price = None  # Reset last buy price when sold
        self.stop_loss_price = None
        self.trailing_stop_price = None
        self.current_stocks = 0  # Reset current_stocks to 0 after selling

    def stop(self):
        # Print the trade history at the end of the backtest
        print("Trade History:")
        for trade in self.trade_history:
            print(f"Action: {trade['action']}, Entry Price: {trade.get('entry_price', 'N/A')}, Exit Price: {trade.get('exit_price', 'N/A')}, Size: {trade['size']}, Profit/Loss: {trade['profit_or_loss']}, Cumulative Capital: {trade['cumulative_capital']}")

        # Save trade history to CSV
        trade_history_df = pd.DataFrame(self.trade_history)
        trade_history_df.to_csv('trade_history_backtrader.csv', index=False)

# Analyzer class for calculating performance metrics (remains unchanged)
class PerformanceAnalyzer(bt.Analyzer):
    def __init__(self):
        self.total_trades = 0

    def notify_trade(self, trade):
        if trade.isclosed:
            self.total_trades += 1

    def get_analysis(self):
        return {
            'total_trades': self.total_trades
        }

# Load data (remains unchanged)
def load_data(data):
    data_feed = bt.feeds.PandasData(dataname=data, datetime='datetime', open='open', high='high', low='low', close='close', volume='volume')
    return data_feed

# Backtest setup function (remains unchanged)
def run_backtest(data):
    cerebro = bt.Cerebro()
    cerebro.addstrategy(EMACrossoverStrategy)

    data_feed = load_data(data)
    cerebro.adddata(data_feed)

    cerebro.addsizer(bt.sizers.FixedSize, stake=1)
    cerebro.broker.setcash(10000)
    print(f"Starting Portfolio Value: {cerebro.broker.getvalue()}")

    # Add analyzers
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(PerformanceAnalyzer, _name='performance')

    # Run the backtest
    result = cerebro.run()

    # Calculate performance metrics (remains unchanged)
    strat = result[0]

    total_return = strat.analyzers.returns.get_analysis()['rtot'] * 100
    market_return = (data['close'].iloc[-1] / data['close'].iloc[0] - 1) * 100
    num_trades = strat.analyzers.performance.get_analysis()['total_trades']
    max_drawdown = strat.analyzers.drawdown.get_analysis()['max']['drawdown']
    avg_trade_return = total_return / num_trades if num_trades > 0 else 0

    # Print the results (remains unchanged)
    print(f"Total Return: {total_return:.2f}%")
    print(f"Market Return: {market_return:.2f}%")
    print(f"Number of Trades: {num_trades}")
    print(f"Max Drawdown: {max_drawdown:.2f}%")
    print(f"Average Return per Trade: {avg_trade_return:.2f}%")

    # Plot the result (remains unchanged)
    cerebro.plot()

# Example usage (remains unchanged)
if __name__ == '__main__':
    # Sample data (replace this with your actual DataFrame)
    data = pd.read_csv('btcusdt_1h.csv', parse_dates=['datetime'])

    # Run the backtest
    run_backtest(data)
