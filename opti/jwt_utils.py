from datetime import timedelta
from .utils import utc_now, create_nickname_from_email

from jose import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyCookie

from .database import async_session_maker
from sqlalchemy import select
from .models import User

from opti.config import SECRET_KEY


API_ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30


CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail='Could not validate credentials',
    headers={'WWW-Authenticate': 'Bearer'},
)


def create_access_token(*, data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = utc_now() + expires_delta
    else:
        expire = utc_now() + timedelta(minutes=15)
    to_encode.update({'exp': expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm='HS256')
    return encoded_jwt


def create_refresh_token(email):
    expires = timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    return create_access_token(data={'sub': email}, expires_delta=expires)


# Create token for an email
def create_token(email):
    access_token_expires = timedelta(minutes=API_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={'sub': email}, expires_delta=access_token_expires)
    return access_token


async def valid_email_from_db(email) -> bool:
    async with async_session_maker() as session:
        if not await session.get(User, email):
            new_user = User(
                email=email,
                nickname=create_nickname_from_email(email),
                is_superuser=False,
            )
            await session.add(new_user)
        query = select(User).where(User.email == email)
        user = await session.execute(query)
        await session.commit()
        return len(user.scalars().all())


def decode_token(token):
    return jwt.decode(token, SECRET_KEY, algorithms=['HS256'])


async def get_current_user_email(token: str = Depends(APIKeyCookie(name='jwt'))):
    try:
        payload = decode_token(token)
        email: str = payload.get('sub')
        if email is None:
            raise CREDENTIALS_EXCEPTION
    except jwt.JWTError:
        raise CREDENTIALS_EXCEPTION

    if await valid_email_from_db(email):
        return email

    raise CREDENTIALS_EXCEPTION