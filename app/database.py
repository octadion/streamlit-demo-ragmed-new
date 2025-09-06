from prisma import Prisma
import os
from dotenv import load_dotenv

load_dotenv()

prisma = Prisma()

async def get_db():
    if not prisma.is_connected():
        await prisma.connect()
    return prisma

async def close_db():
    if prisma.is_connected():
        await prisma.disconnect()