from app.schemas.user_schemas import (
    UserBase, UserCreate, UserLogin, UserResponse,
    MahasiswaBase, MahasiswaCreate, MahasiswaResponse,
    DosenBase, DosenCreate, DosenResponse,
    Token, TokenData,
    CaptchaResponse, LoginWithCaptcha,
    ForgotPasswordRequest, VerifyCodeRequest, ResetPasswordRequest,
    ProfileUpdateRequest, ChangePasswordRequest
)

from app.schemas.document_schemas import (
    TagBase, TagCreate, TagResponse,
    KataKunciBase, KataKunciResponse,
    ReferensiBase, ReferensiCreate, ReferensiResponse, ReferensiValidationRequest,
    CatatanBase, CatatanCreate, CatatanUpdate, CatatanResponse,
    DokumenBase, DokumenCreate, DokumenResponse, DokumenDetailResponse,
    KeywordExtractionRequest, KeywordExtractionResponse,
    SummarizationRequest, SummarizationResponse,
    DocumentNode, DocumentEdge, VisualizationResponse
)

__all__ = [
    # User schemas
    "UserBase", "UserCreate", "UserLogin", "UserResponse",
    "MahasiswaBase", "MahasiswaCreate", "MahasiswaResponse",
    "DosenBase", "DosenCreate", "DosenResponse",
    "Token", "TokenData",
    
    # Auth schemas - CAPTCHA & Forgot Password
    "CaptchaResponse", "LoginWithCaptcha",
    "ForgotPasswordRequest", "VerifyCodeRequest", "ResetPasswordRequest",
    "ProfileUpdateRequest", "ChangePasswordRequest",
    
    # Document schemas
    "TagBase", "TagCreate", "TagResponse",
    "KataKunciBase", "KataKunciResponse",
    "ReferensiBase", "ReferensiCreate", "ReferensiResponse", "ReferensiValidationRequest",
    "CatatanBase", "CatatanCreate", "CatatanUpdate", "CatatanResponse",
    "DokumenBase", "DokumenCreate", "DokumenResponse", "DokumenDetailResponse",
    
    # NLP schemas
    "KeywordExtractionRequest", "KeywordExtractionResponse",
    "SummarizationRequest", "SummarizationResponse",
    
    # Visualization schemas
    "DocumentNode", "DocumentEdge", "VisualizationResponse"
]
