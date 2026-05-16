class Transaction:
    """Represents a single trade transaction (buy or sell)."""

    def __init__(self, date, type, price, shares, cost_basis=0.0, realized_profit_loss=0.0):
        self.date = date
        self.type = type  # 'BUY' or 'SELL'
        self.price = price  # Executed price (includes slippage)
        self.shares = shares
        self.cost_basis = cost_basis  # Total cost for BUY; Cost basis of shares sold for SELL
        self.realized_profit_loss = realized_profit_loss  # Only for SELL trades

    def __repr__(self):
        return (f"Transaction(date={self.date.strftime('%Y-%m-%d')}, "
                f"type='{self.type}', price={self.price:.2f}, shares={self.shares}, "
                f"P/L={self.realized_profit_loss:.2f})")

    def to_dict(self):
        return {
            'date': self.date,
            'type': self.type,
            'price': self.price,
            'shares': self.shares,
            'cost_basis': self.cost_basis,
            'profit_loss': self.realized_profit_loss,
        }
