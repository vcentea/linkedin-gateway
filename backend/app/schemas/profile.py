"""
Pydantic schemas for profiles.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class ProfileBase(BaseModel):
    """Base schema for profile data."""
    linkedin_id: str = Field(..., description="LinkedIn profile ID")
    name: Optional[str] = Field(None, description="Full name")
    jobtitle: Optional[str] = Field(None, description="Job title")
    about: Optional[str] = Field(None, description="About section")
    industry: Optional[str] = Field(None, description="Industry")
    company: Optional[str] = Field(None, description="Company")
    location: Optional[str] = Field(None, description="Location")
    skills: Optional[str] = Field(None, description="Skills")
    courses: Optional[List[str]] = Field(default_factory=list, description="Courses")
    certifications: Optional[List[str]] = Field(default_factory=list, description="Certifications")
    department: Optional[str] = Field(None, description="Department")
    level: Optional[str] = Field(None, description="Level")
    vanity_name: Optional[str] = Field(None, description="LinkedIn vanity name (from URL)")
    areasofinterest: Optional[str] = Field(None, description="Areas of interest")
    positions: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Positions")
    education: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Education")
    languages: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Languages")
    profile_url: Optional[str] = Field(None, description="Profile URL")
    profile_score: Optional[float] = Field(None, description="Profile score")
    full_info_scraped: bool = Field(False, description="Whether full info has been scraped")
    writing_style: Optional[str] = Field(None, description="Writing style")
    personality: Optional[str] = Field(None, description="Personality")
    strengths: Optional[str] = Field(None, description="Strengths")
    keywords: Optional[List[str]] = Field(default_factory=list, description="Keywords")
    added_by_userid: Optional[UUID] = Field(None, description="ID of user who added the profile")
    recommendations: Optional[List[str]] = Field(default_factory=list, description="Recommendations")
    last_20_posts: Optional[List[str]] = Field(default_factory=list, description="Last 20 posts")
    last_20_comments: Optional[List[str]] = Field(default_factory=list, description="Last 20 comments")
    highlighted_posts: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Highlighted posts")
    commentators_list: Optional[List[str]] = Field(default_factory=list, description="List of commentators")
    reactors_list: Optional[List[str]] = Field(default_factory=list, description="List of reactors")
    profile_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional profile metadata")


class ProfileCreate(ProfileBase):
    """Schema for creating a new profile."""
    pass


class ProfileUpdate(ProfileBase):
    """Schema for updating an existing profile."""
    pass


class ProfileInDB(ProfileBase):
    """Schema for profile data as stored in the database."""
    id: int = Field(..., description="Database ID of the profile")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


# New schemas for profile scraping endpoint

class ScrapeProfileRequest(BaseModel):
    """Request schema for scraping a LinkedIn profile."""
    profile_id: str = Field(..., description="LinkedIn profile ID or URL (e.g., 'ACoAACMM5dYB...' or 'https://www.linkedin.com/in/username/')")
    api_key: Optional[str] = Field(default=None, description="The user's full API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use WebSocket client")


class ProfileExperience(BaseModel):
    """Schema for a single work experience."""
    company: str
    role: str
    time_duration: str
    time_period: Optional[str] = None
    duration: Optional[str] = None
    description: str


class ProfileEducation(BaseModel):
    """Schema for a single education entry."""
    schoolName: str
    degreeName: str
    fieldOfStudy: str
    startDate: Any  # Can be dict or string
    endDate: Any  # Can be dict or string


class ProfileLanguage(BaseModel):
    """Schema for a single language entry."""
    name: str
    proficiency: str


class ScrapeProfileResponse(BaseModel):
    """
    Clean response schema for profile scraping.
    
    Data sources:
    - Identity Cards (GraphQL): vanity_name, firstName, lastName, follower_count
    - Contact Info (GraphQL): email, phone, website, birthday, connected_date
    - HTML Page: headline, location, con_degree
    - About & Skills (GraphQL): about, skills
    """
    # Identity
    linkedin_id: str
    vanity_name: str
    profile_url: str
    name: str
    firstName: str
    lastName: str
    
    # HTML scraped
    headline: str
    con_degree: str
    location: str
    
    # About & Skills
    about: str
    skills: List[str]
    
    # Contact Info
    email: str
    phone: str
    website: str
    birthday: str
    connected_date: str
    
    # Follower count
    follower_count: int = Field(default=0, description="Number of followers")


class ScrapeProfileExperiencesRequest(BaseModel):
    """Request schema for scraping profile experiences."""
    profile_id: str = Field(..., description="LinkedIn profile ID or URL")
    api_key: Optional[str] = Field(default=None, description="The user's full API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use WebSocket client")


class ScrapeProfileExperiencesResponse(BaseModel):
    """Response schema for profile experiences."""
    experiences: List[ProfileExperience]


class ScrapeProfileRecommendationsRequest(BaseModel):
    """Request schema for scraping profile recommendations."""
    profile_id: str = Field(..., description="LinkedIn profile ID or URL")
    api_key: Optional[str] = Field(default=None, description="The user's full API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use WebSocket client")


class ScrapeProfileRecommendationsResponse(BaseModel):
    """Response schema for profile recommendations."""
    recommendations: List[str]


class ScrapeProfileIdentityRequest(BaseModel):
    """Request schema for scraping profile identity data."""
    profile_id: str = Field(..., description="LinkedIn profile ID or URL")
    api_key: Optional[str] = Field(default=None, description="The user's full API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use WebSocket client")


class ScrapeProfileIdentityResponse(BaseModel):
    """Response schema for profile identity data (identity cards + HTML data)."""
    linkedin_id: str
    vanity_name: str
    profile_url: str
    first_name: str
    last_name: str
    name: str
    headline: str
    location: str
    con_degree: str
    follower_count: int = Field(default=0)


class ScrapeProfileContactRequest(BaseModel):
    """Request schema for scraping profile contact information."""
    profile_id: str = Field(..., description="LinkedIn profile ID or URL")
    api_key: Optional[str] = Field(default=None, description="The user's full API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use WebSocket client")


class ScrapeProfileContactResponse(BaseModel):
    """Response schema for profile contact information."""
    email: str
    phone: str
    website: str
    birthday: str
    connected_date: str


class ScrapeProfileAboutSkillsRequest(BaseModel):
    """Request schema for scraping profile about section and skills."""
    profile_id: str = Field(..., description="LinkedIn profile ID or URL")
    api_key: Optional[str] = Field(default=None, description="The user's full API key (optional if provided via X-API-Key header)")
    server_call: bool = Field(False, description="If true, execute on server; if false, use WebSocket client")


class ExperienceEntry(BaseModel):
    """Schema for a single experience entry."""
    title: str = Field(default="", description="Job title")
    company: str = Field(default="", description="Company name")
    employment_type: str = Field(default="", description="Employment type (Full-time, Part-time, etc.)")
    dates: str = Field(default="", description="Employment dates")
    location: str = Field(default="", description="Location")
    description: str = Field(default="", description="Job description")


class RecommendationEntry(BaseModel):
    """Schema for a single recommendation entry."""
    recommender_name: str = Field(default="", description="Name of the person who gave the recommendation")
    recommender_title: str = Field(default="", description="Title/position of the recommender")
    recommendation_text: str = Field(default="", description="The recommendation text")


class LanguageEntry(BaseModel):
    """Schema for a single language entry."""
    name: str = Field(default="", description="Language name")
    proficiency: str = Field(default="", description="Proficiency level")


class ScrapeProfileAboutSkillsResponse(BaseModel):
    """Response schema for profile about section, skills, and languages."""
    about: str
    skills: List[str]
    languages: List[LanguageEntry] = Field(default_factory=list, description="Languages and proficiency levels") 