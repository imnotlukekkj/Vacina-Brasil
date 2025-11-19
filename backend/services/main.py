import psycopg
from dotenv import load_dotenv
import os
import logging

# Load environment variables from .env
load_dotenv()

# Fetch variables
USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")

logger = logging.getLogger(__name__)


def main():
    # Connect to the database
    try:
        # psycopg (v3) uses a very similar connect signature
        connection = psycopg.connect(
            user=USER,
            password=PASSWORD,
            host=HOST,
            port=PORT,
            dbname=DBNAME
        )
        logger.info("Connection successful")
        
        # Create a cursor to execute SQL queries
        cursor = connection.cursor()
        
        # Example query
        cursor.execute("SELECT NOW();")
        result = cursor.fetchone()
        logger.info("Current Time: %s", result)

        # Close the cursor and connection
        cursor.close()
        connection.close()
        logger.info("Connection closed")

    except Exception as e:
        logger.exception("Failed to connect: %s", e)


if __name__ == "__main__":
    main()
