/*
**	Command & Conquer Generals Zero Hour(tm)
**	Copyright 2025 Electronic Arts Inc.
**
**	This program is free software: you can redistribute it and/or modify
**	it under the terms of the GNU General Public License as published by
**	the Free Software Foundation, either version 3 of the License, or
**	(at your option) any later version.
**
**	This program is distributed in the hope that it will be useful,
**	but WITHOUT ANY WARRANTY; without even the implied warranty of
**	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
**	GNU General Public License for more details.
**
**	You should have received a copy of the GNU General Public License
**	along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

// FILE: OpenALAudioManager.h //////////////////////////////////////////////////////////////////////////
// OpenALAudioManager implementation
// Author: Stephan Vedder, March 2025
#pragma once
#include "Common/AsciiString.h"
#include "Common/GameAudio.h"
#include <AL/al.h>
#include <AL/alc.h>

class AudioEventRTS;

enum
{
	MAXPROVIDERS = 64
};

#define AL_MAX_PLAYBACK_DEVICES 64

enum PlayingAudioType
{
	PAT_Sample,
	PAT_3DSample,
	PAT_Stream,
	PAT_INVALID
};

enum PlayingWhich
{
	PW_Attack,
	PW_Sound,
	PW_Decay,
	PW_INVALID
};

struct ProviderInfo
{
	AsciiString name;
	Bool m_isValid;
};

struct PlayingAudio;
struct OpenALAudioFileCache;
class OpenALAudioStream;

class OpenALAudioManager : public AudioManager
{
friend class OpenALAudioStream;
friend class FFmpegVideoStream;
friend class OpenALAudioFileCache;

public:
#if defined(_DEBUG) || defined(_INTERNAL)
	virtual void audioDebugDisplay(DebugDisplayInterface *dd, void *, FILE *fp = NULL);
	virtual AudioHandle addAudioEvent(const AudioEventRTS *eventToAdd); ///< Add an audio event (event must be declared in an INI file)
#endif

	// from AudioDevice
	// GeneralsX @build Codex 31/10/2026 Make the existing virtual overrides explicit.
	virtual void init() override;
	virtual void postProcessLoad() override;
	virtual void reset() override;
	virtual void update() override;

	OpenALAudioManager();
	virtual ~OpenALAudioManager();

	virtual AsciiString nextMusicTrack(void) override;
	virtual AsciiString prevMusicTrack(void) override;
	virtual Bool isMusicPlaying(void) const override;
	virtual Bool hasMusicTrackCompleted(const AsciiString &trackName, Int numberOfTimes) const override;

	virtual void openDevice(void) override;
	virtual void closeDevice(void) override;
	virtual void *getDevice(void) override { return m_alcDevice; }

	virtual void stopAudio(AudioAffect which) override;
	virtual void pauseAudio(AudioAffect which) override;
	virtual void resumeAudio(AudioAffect which) override;
	virtual void pauseAmbient(Bool shouldPause) override;

	virtual void killAudioEventImmediately(AudioHandle audioEvent) override;

	///< Return whether the current audio is playing or not.
	///< NOTE NOTE NOTE !!DO NOT USE THIS IN FOR GAMELOGIC PURPOSES!! NOTE NOTE NOTE
	virtual Bool isCurrentlyPlaying(AudioHandle handle) override;

	virtual void notifyOfAudioCompletion(ALuint source, UnsignedInt flags) override;
	virtual PlayingAudio *findPlayingAudioFrom(ALuint source, UnsignedInt flags);

	virtual UnsignedInt getProviderCount(void) const override;
	virtual AsciiString getProviderName(UnsignedInt providerNum) const override;
	virtual UnsignedInt getProviderIndex(AsciiString providerName) const override;
	virtual void selectProvider(UnsignedInt providerNdx) override;
	virtual void unselectProvider(void) override;
	virtual UnsignedInt getSelectedProvider(void) const override;
	virtual void setSpeakerType(UnsignedInt speakerType) override;
	virtual UnsignedInt getSpeakerType(void) override;

	virtual void *getHandleForBink(void) override;
	virtual void releaseHandleForBink(void) override;

	virtual void friend_forcePlayAudioEventRTS(const AudioEventRTS *eventToPlay) override;

	virtual UnsignedInt getNum2DSamples(void) const override;
	virtual UnsignedInt getNum3DSamples(void) const override;
	virtual UnsignedInt getNumStreams(void) const override;

	virtual Bool doesViolateLimit(AudioEventRTS *event) const override;
	virtual Bool isPlayingLowerPriority(AudioEventRTS *event) const override;
	virtual Bool isPlayingAlready(AudioEventRTS *event) const override;
	virtual Bool isObjectPlayingVoice(UnsignedInt objID) const override;
	Bool killLowestPrioritySoundImmediately(AudioEventRTS *event);
	AudioEventRTS *findLowestPrioritySound(AudioEventRTS *event);

	virtual void adjustVolumeOfPlayingAudio(AsciiString eventName, Real newVolume) override;

	virtual void removePlayingAudio(AsciiString eventName) override;
	virtual void removeAllDisabledAudio() override;

	virtual void processRequestList(void) override;
	virtual void processPlayingList(void);
	virtual void processFadingList(void);
	virtual void processStoppedList(void);

	Bool shouldProcessRequestThisFrame(AudioRequest *req) const;
	void adjustRequest(AudioRequest *req);
	Bool checkForSample(AudioRequest *req);

	virtual void setHardwareAccelerated(Bool accel) override;
	virtual void setSpeakerSurround(Bool surround) override;

	virtual void setPreferredProvider(AsciiString provider) override { m_pref3DProvider = provider; }
	virtual void setPreferredSpeaker(AsciiString speakerType) override { m_prefSpeaker = speakerType; }

	virtual Real getFileLengthMS(AsciiString strToLoad) const override;

	virtual void closeAnySamplesUsingFile(const void *fileToClose) override;

	virtual Bool has3DSensitiveStreamsPlaying(void) const override;

protected:
	// 3-D functions
	virtual void setDeviceListenerPosition(void) override;
	const Coord3D *getCurrentPositionFromEvent(AudioEventRTS *event);
	Bool isOnScreen(const Coord3D *pos) const;
	Real getEffectiveVolume(AudioEventRTS *event) const;

	// Looping functions
	Bool startNextLoop(PlayingAudio *looping);

	void playStream(AudioEventRTS *event, OpenALAudioStream* stream);
	// Returns the buffer handle representing audio data for attachment to the PlayingAudio structure
	ALuint playSample(AudioEventRTS *event, PlayingAudio *audio);
	ALuint playSample3D(AudioEventRTS *event, PlayingAudio * audio);

protected:
	void enumerateDevices(void);
	void createListener(void);
	void initDelayFilter(void);
	Bool isValidProvider(void);
	void initSamplePools(void);
	void processRequest(AudioRequest *req);

	void playAudioEvent(AudioEventRTS *event);
	void stopAudioEvent(AudioHandle handle);
	void pauseAudioEvent(AudioHandle handle);

	ALuint loadBufferForRead(AudioEventRTS *eventToLoadFrom);
	void closeBuffer(ALuint bufferToClose);

	PlayingAudio *allocatePlayingAudio(void);
	void releaseOpenALHandles(PlayingAudio *release);
	void releasePlayingAudio(PlayingAudio *release);

	void stopAllAudioImmediately(void);
	void freeAllOpenALHandles(void);

	PlayingAudio *getFirst2DSample(AudioEventRTS *event);
	PlayingAudio *getFirst3DSample(AudioEventRTS *event);

	void adjustPlayingVolume(PlayingAudio *audio);

	void stopAllSpeech(void);
    static ALenum getALFormat(uint8_t channels, uint8_t bitsPerSample);
protected:
	AsciiString m_alDevicesList[AL_MAX_PLAYBACK_DEVICES];
	int m_alMaxDevicesIndex;

	ProviderInfo m_provider3D[MAXPROVIDERS];
	UnsignedInt m_providerCount;
	UnsignedInt m_selectedProvider;
	UnsignedInt m_lastProvider;
	UnsignedInt m_selectedSpeakerType;

	AsciiString m_pref3DProvider;
	AsciiString m_prefSpeaker;

	// Currently Playing stuff. Useful if we have to preempt it.
	// This should rarely if ever happen, as we mirror this in Sounds, and attempt to
	// keep preemption from taking place here.
	std::list<PlayingAudio *> m_playingSounds;
	std::list<PlayingAudio *> m_playing3DSounds;
	std::list<PlayingAudio *> m_playingStreams;

	// Currently fading stuff. At this point, we just want to let it finish fading, when it is
	// done it should be added to the completed list, then "freed" and the counts should be updated
	// on the next update
	std::list<PlayingAudio *> m_fadingAudio;

	// Stuff that is done playing (either because it has finished or because it was killed)
	// This stuff should be cleaned up during the next update cycle. This includes updating counts
	// in the sound engine
	std::list<PlayingAudio *> m_stoppedAudio;

	OpenALAudioFileCache *m_audioCache;
	UnsignedInt m_num2DSamples;
	UnsignedInt m_num3DSamples;
	UnsignedInt m_numStreams;

#if defined(_DEBUG) || defined(_INTERNAL)
	typedef std::set<AsciiString> SetAsciiString;
	typedef SetAsciiString::iterator SetAsciiStringIt;
	SetAsciiString m_allEventsLoaded;
	void dumpAllAssetsUsed();
#endif

	ALCdevice *m_alcDevice = nullptr;
	ALCcontext *m_alcContext = nullptr;
	OpenALAudioStream* m_binkAudio = nullptr;
};
