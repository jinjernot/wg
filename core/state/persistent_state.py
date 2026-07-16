# This module is superseded. Last-processed message IDs are now stored
# directly inside each trade's state dict (as 'last_processed_message_id')
# and persisted via core.state.trade_state_loader.save_processed_trade().
#
# This file is kept as a tombstone to explain the migration.
# Do NOT import or use load_last_message_ids / save_last_message_id.