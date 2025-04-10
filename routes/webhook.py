from fastapi import APIRouter, HTTPException
from models.webhook import WebhookRequest
import httpx
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

router = APIRouter(
    prefix="/webhook",
    tags=["webhook"]
)

@router.post("/trigger")
async def trigger_webhook(request: WebhookRequest):
    try:
        print("Received webhook request:", request.dict())
        # Get the webhook URL from environment variables
        webhook_url = os.getenv("N8N_WEBHOOK_URL")
        if not webhook_url:
            raise HTTPException(
                status_code=500,
                detail="N8N_WEBHOOK_URL environment variable is not set"
            )

        print("\nUsing webhook URL:", webhook_url)
        
        # Make the request to n8n webhook
        # Configure longer timeouts since n8n might need time to process
        timeout = httpx.Timeout(
            timeout=120.0,     # Total timeout
            connect=30.0,      # Connection timeout
            read=90.0,        # Read timeout
            write=30.0        # Write timeout
        )
        
        try:
            print(f"\nConnecting to n8n with timeouts: connect={timeout.connect}s, read={timeout.read}s")
            
            transport = httpx.AsyncHTTPTransport(
                retries=2,            # Number of retries
                verify=False,         # Disable SSL verification temporarily
            )
            
            # Configure client with updated settings
            async with httpx.AsyncClient(
                timeout=timeout,
                transport=transport,
                follow_redirects=True
            ) as client:
                print("Sending data to n8n:", request.data)
                response = await client.post(
                    webhook_url,
                    json=request.data,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                )
                
                print("n8n response status:", response.status_code)
                print("n8n content-type:", response.headers.get("content-type"))
                print("n8n response body:", response.text)
                
                if not response.is_success:
                    print("n8n error response body:", response.text)
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Failed to trigger workflow: {response.status_code}. Body: {response.text}"
                    )
        except httpx.ReadTimeout as e:
            error_msg = "Request timed out while waiting for n8n response"
            print(f"\nTimeout Error Details:")
            print(f"Error type: {type(e).__name__}")
            print(f"Timeout settings: connect={timeout.connect}s, read={timeout.read}s")
            print(f"Attempted URL: {webhook_url}")
            raise HTTPException(
                status_code=504,  # Gateway Timeout
                detail="The request to n8n timed out. The workflow might still be processing."
            )
        except httpx.RequestError as e:
            error_msg = f"HTTP Request failed: {str(e)}"
            print(f"\nDetailed error information:")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print(f"Attempted URL: {webhook_url}")
            print(f"Request method: POST")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to connect to n8n: {error_msg}"
            )
            
        except Exception as e:
            error_msg = f"Unexpected error during request: {str(e)}"
            print(error_msg)
            raise HTTPException(
                status_code=500,
                detail=f"Error connecting to n8n: {error_msg}"
            )

        # Parse the response data
        try:
            response_data = response.json()
        except Exception as e:
            print("Failed to parse response as JSON:", response.text)
            raise HTTPException(
                status_code=500,
                detail=f"Invalid JSON response from n8n: {response.text}"
            )
        print("n8n response:", response_data)

        # Extract the PDF URL from the response
        pdf_url = response_data.get('pdfUrl')

        if not pdf_url:
            print('No PDF URL in response:', response_data)
            raise HTTPException(
                status_code=400,
                detail='No itinerary link found in the response'
            )

        return {"message": "Trip itinerary generated successfully", "status": "success", "pdfUrl": pdf_url}

    except HTTPException as he:
        raise he
    except Exception as e:
        print("Webhook error:", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Error triggering webhook: {str(e)}"
        )
