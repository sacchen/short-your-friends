from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict

STEPS_REWARD_RATE = Decimal("0.01")  # Credits per step
DOOMSCROLL_TAX_RATE = Decimal("5.00")  # Credits burned per hour


@dataclass
class Account:
    user_id: str
    # Total equity = available + locked
    balance_available: Decimal = field(default_factory=lambda: Decimal("0.00"))
    balance_locked: Decimal = field(
        default_factory=lambda: Decimal("0.00")
    )  # Money in active buy orders

    def total_equity(self) -> Decimal:
        # result: Decimal = self.balance_available + self.balance_locked
        return self.balance_available + self.balance_locked


class EconomyManager:
    def __init__(self) -> None:
        self.accounts: Dict[str, Account] = {}

    def get_account(self, user_id: str) -> Account:
        if user_id not in self.accounts:
            self.accounts[user_id] = Account(user_id=user_id)
        return self.accounts[user_id]

    # Game Mechanics (Mint/Burn)

    def process_proof_of_walk(self, user_id: str, steps: int) -> Decimal:
        """
        Mints new credits based on walking.
        Returns the amount minted.
        """
        account = self.get_account(user_id)
        reward = Decimal(steps) * STEPS_REWARD_RATE
        account.balance_available += reward
        return reward
        # print(f"User {user_id} walked {steps} steps. Minted {reward} credits.")

    def process_doomscroll_burn(self, user_id: str, minutes: int) -> Decimal:
        """
        Burns credits based on screen time.
        Returns the amount burned.
        """
        account = self.get_account(user_id)
        # Calculate tax: (minutes / 60) * hourly_rate
        tax = (Decimal(minutes) / Decimal(60)) * DOOMSCROLL_TAX_RATE

        tax = tax.quantize(Decimal("0.01"))  # Rounds to 2 decimal places.

        # No debt: Floor at zero.
        if account.balance_available >= tax:
            account.balance_available -= tax
        else:
            tax = account.balance_available  # Burned amount is whatever was left
            account.balance_available = Decimal("0.00")
            # Can trigger Bankrupt state in future

        # print(f"User {user_id} doomscrolled {minutes} mins. Burned {tax} credits.")
        return tax

    # Trading: Check logic

    def attempt_order_lock(self, user_id: str, price: Decimal, quantity: int) -> bool:
        """
        Called before an order is sent to matching engine.
        Returns True if funds were successfully locked.
        """
        account = self.get_account(user_id)
        cost = price * Decimal(quantity)

        if account.balance_available >= cost:
            account.balance_available -= cost
            account.balance_locked += cost
            return True
        return False

    def release_order_lock(self, user_id: str, price: Decimal, quantity: int) -> None:
        """
        Called if an order is cancelled or expires.
        Returns funds from locked to available.
        """
        account = self.get_account(user_id)
        cost = price * Decimal(quantity)

        # Prevent negative locked balance
        if account.balance_locked >= cost:
            account.balance_locked -= cost
            account.balance_available += cost

    def confirm_trade(
        self, buyer_id: str, seller_id: str, price: Decimal, quantity: int
    ) -> None:
        """
        Called when a trade executes.
        Buyer: Locked funds are removed/spent.
        Seller: Funds are added to available balance.
        """
        cost = price * Decimal(quantity)

        # Buyer (funds were already locked)
        buyer = self.get_account(buyer_id)
        buyer.balance_locked -= cost
        # TODO: In database, assert >0

        # Seller gets paid
        seller = self.get_account(seller_id)
        seller.balance_available += cost

    def distribute_ubi(self, amount: Decimal = Decimal("100.00")) -> None:
        """Give everyone their daily bread."""
        for user_id in self.accounts:
            self.accounts[user_id].balance_available += amount
        # TODO: need database/timestamp log of last distribution
        # so function doesn't run every time server restarts

    # save to JSON for Persistence
    def dump_state(self) -> Dict[str, Dict[str, str]]:
        """Export all accounts to dictionary."""
        return {
            user_id: {
                "available": str(acc.balance_available),
                "locked": str(acc.balance_locked),
            }
            for user_id, acc in self.accounts.items()  # keys, values
            # acc is the Value (`Account` object)
        }

    def load_state(self, data: Dict[str, Dict[str, str]]) -> None:
        """Restore accounts from dictionary."""
        self.accounts.clear()
        for user_id, balances in data.items():
            acc = Account(user_id=user_id)
            acc.balance_available = Decimal(balances["available"])
            acc.balance_locked = Decimal(balances["locked"])
            self.accounts[user_id] = acc
