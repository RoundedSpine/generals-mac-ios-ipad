#pragma once

// GeneralsX @feature Codex 29/10/2026 Preserve every transient admission decision with an exact bounded interval of permanent usage.
template<unsigned Capacity>
class SearchAdmissionWindow {
 static_assert(Capacity>0,"Search admission needs a positive capacity");
 unsigned m_lower=0,m_upper=Capacity,m_captured=0;
 bool m_observed=false,m_valid=true;
public:
 void reset(){m_lower=0;m_upper=Capacity;m_captured=0;m_observed=false;m_valid=true;}
 bool allows(unsigned permanent,unsigned transient){
  if(permanent>Capacity || transient>Capacity){m_valid=false;return false;}
  if(!m_observed){m_captured=permanent;m_observed=true;}
  else if(m_captured!=permanent)m_valid=false;
  const bool allowed=permanent<Capacity-transient;
  if(allowed){
   const unsigned upper=Capacity-transient-1;
   if(upper<m_upper)m_upper=upper;
  }else{
   const unsigned lower=Capacity-transient;
   if(lower>m_lower)m_lower=lower;
  }
  if(m_lower>m_upper)m_valid=false;
  return allowed;
 }
 bool matches(unsigned captured,unsigned current)const{
  return m_valid && captured<=Capacity && current<=Capacity &&
   (!m_observed || captured==m_captured) && current>=m_lower && current<=m_upper;
 }
 unsigned lower()const{return m_lower;}
 unsigned upper()const{return m_upper;}
 bool valid()const{return m_valid;}
 bool observed()const{return m_observed;}
};
