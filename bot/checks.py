from discord import app_commands, Interaction
from config import DISCORD_ADMIN_ROLE_ID
import logging

logger = logging.getLogger(__name__)

def is_admin():
    """
    A check to see if the user has the admin role specified in the config.
    """
    def predicate(interaction: Interaction) -> bool:
        if not DISCORD_ADMIN_ROLE_ID:
            logger.warning("DISCORD_ADMIN_ROLE_ID is not set. Denying command access.")
            return False
            
        # The user's roles are available in the Interaction object.
        admin_role = interaction.guild.get_role(DISCORD_ADMIN_ROLE_ID)
        
        if admin_role is None:
            logger.warning(f"Could not find the admin role with ID {DISCORD_ADMIN_ROLE_ID} in the server.")
            return False

        # Check if the admin role is in the user's list of roles.
        if admin_role in interaction.user.roles:
            return True
        else:
            # Optionally, send an ephemeral message to the user who failed the check.
            # await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            logger.warning(f"User {interaction.user} (ID: {interaction.user.id}) tried to use an admin command without permission.")
            return False
            
    return app_commands.check(predicate)