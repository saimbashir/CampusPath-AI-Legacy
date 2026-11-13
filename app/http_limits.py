"""Bound request bodies even when Content-Length is absent or incorrect."""
from starlette.responses import JSONResponse
class BodyLimitMiddleware:
    def __init__(self,app,limit=9*1024*1024):self.app=app;self.limit=limit
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope.get('method') in ('GET','HEAD','OPTIONS'):
            return await self.app(scope,receive,send)
        data=bytearray()
        while True:
            message=await receive()
            if message['type']=='http.disconnect':return
            data.extend(message.get('body',b''))
            if len(data)>self.limit:
                return await JSONResponse({'detail':'Request exceeds the size limit.'},status_code=413)(scope,receive,send)
            if not message.get('more_body',False):break
        delivered=False
        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered=True;return {'type':'http.request','body':bytes(data),'more_body':False}
            return await receive()
        await self.app(scope,bounded_receive,send)
