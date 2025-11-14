"""
Database Schemas for CTF Application

Each Pydantic model corresponds to a MongoDB collection (collection name = lowercase class name).
"""
from pydantic import BaseModel, Field
from typing import Optional, List

class Ctfuser(BaseModel):
    username: str = Field(..., description="Display name of the user")
    email: str = Field(..., description="Login email")
    password: str = Field(..., description="Plain password for demo only (do not use in production)")
    score: int = Field(0, description="Accumulated score from solved challenges")
    solved: List[str] = Field(default_factory=list, description="List of solved challenge IDs as strings")

class Challenge(BaseModel):
    title: str = Field(..., description="Challenge title")
    category: str = Field(..., description="Category like Web, Forensics, Crypto, Pwn")
    difficulty: str = Field(..., description="Easy | Medium | Hard")
    points: int = Field(..., ge=0, description="Score for solving")
    description: str = Field(..., description="Challenge description/statement")
    flag: str = Field(..., description="Correct flag format: CTF{...}")

class Submission(BaseModel):
    user_id: str = Field(..., description="User ObjectId as string")
    challenge_id: str = Field(..., description="Challenge ObjectId as string")
    flag: str = Field(..., description="Submitted flag")
    correct: bool = Field(False, description="Whether the submission is correct")
