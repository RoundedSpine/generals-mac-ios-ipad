/*
**	Command & Conquer Generals Zero Hour(tm)
**	Copyright 2025 TheSuperHackers
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

////////////////////////////////////////////////////////////////////////////////
//																																						//
//  (c) 2001-2003 Electronic Arts Inc.																				//
//																																						//
////////////////////////////////////////////////////////////////////////////////

//////// FFmpegVideoPlayer.h ///////////////////////////
// Stephan Vedder, April 2025
/////////////////////////////////////////////////

#pragma once

//----------------------------------------------------------------------------
//           Includes
//----------------------------------------------------------------------------

#include "GameClient/VideoPlayer.h"

//----------------------------------------------------------------------------
//           Forward References
//----------------------------------------------------------------------------

class FFmpegFile;
struct AVFrame;
struct SwsContext;

//----------------------------------------------------------------------------
//           Type Defines
//----------------------------------------------------------------------------

//===============================
// FFmpegVideoStream
//===============================

// GeneralsX @build Codex 01/11/2026 Check shared video override signatures at compile time.
class FFmpegVideoStream : public VideoStream
{
	friend class FFmpegVideoPlayer;

	protected:
		Bool 			m_good = true;			///< Is the stream valid
		Bool 			m_gotFrame = false;		///< Is the frame ready to be displayed
		AVFrame 		*m_frame = nullptr;		///< Current frame
		SwsContext 		*m_swsContext = nullptr;///< SWSContext for scaling
		FFmpegFile		*m_ffmpegFile;			///< The AVUI abstraction											///< Bink streaming handle;
		Char			*m_memFile;				///< Pointer to memory resident file
		UnsignedInt64	m_startTime = 0;		///< Time the stream started
		UnsignedByte *	m_audioBuffer = nullptr;///< Audio buffer for the stream

		FFmpegVideoStream(FFmpegFile* file);																///< only BinkVideoPlayer can create these
		virtual ~FFmpegVideoStream() override;

		static void onFrame(AVFrame *frame, int stream_idx, int stream_type, void *user_data);
	public:

		virtual void update() override;											///< Update bink stream

		virtual Bool	isFrameReady() override;								///< Is the frame ready to be displayed
		virtual void	frameDecompress() override;						///< Render current frame in to buffer
		virtual void	frameRender( VideoBuffer *buffer ) override; ///< Render current frame in to buffer
		virtual void	frameNext() override;									///< Advance to next frame
		virtual Int		frameIndex() override;									///< Returns zero based index of current frame
		virtual Int		frameCount() override;									///< Returns the total number of frames in the stream
		virtual void	frameGoto( Int index ) override;							///< Go to the spcified frame index
		virtual Int		height() override;											///< Return the height of the video
		virtual Int		width() override;											///< Return the width of the video


};

//===============================
// FFmpegVideoPlayer
//===============================
/**
  *	FFmpeg video playback code.
	*/
//===============================

class FFmpegVideoPlayer : public VideoPlayer
{

	protected:

		VideoStreamInterface* createStream( File* file );

	public:

		// subsytem requirements
		virtual void	init() override;														///< Initialize video playback code
		virtual void	reset() override;													///< Reset video playback
		virtual void	update() override;													///< Services all audio tasks. Should be called frequently

		virtual void	deinit() override;													///< Close down player


		FFmpegVideoPlayer();
		~FFmpegVideoPlayer() override;

		// service
		virtual void	loseFocus() override;											///< Should be called when application loses focus
		virtual void	regainFocus() override;										///< Should be called when application regains focus

		virtual VideoStreamInterface*	open( AsciiString movieTitle ) override;	///< Open video file for playback
		virtual VideoStreamInterface*	load( AsciiString movieTitle ) override;	///< Load video file in to memory for playback

		virtual void notifyVideoPlayerOfNewProvider( Bool nowHasValid ) override;
		virtual void initializeBinkWithMiles();
};


//----------------------------------------------------------------------------
//           Inlining
//----------------------------------------------------------------------------
