---
layout: page
title: IMC Message
description: ~
---
# Overview
The IMC establishes a common control message set understood by all LSTS nodes. It was developed at the LSTS and it is pervasive in the LSTS ecosystem, as it enables communication among interconnected systems of vehicles, sensors, DUNE tasks, and even other layers of the control architecture, such as the Neptus. 

IMC abstracts hardware and communication differences, providing a shared set of messages that can be serialized and then exchanged using various means. Unlike other protocols, IMC does not impose a specific software architecture, allowing for native support generation across different programming languages and computer architectures. The message specification is an XML file that can be found in the repository of the LSTS. It should contain all the necessary information to serialize and deserialize messages exchanged in the network.

# Parts of the Message

## Header:

The message header is tuple of
* Synchronization Number (16 bit unsigned integer): Used to mark the begin of a message in the byte stream;
* Message Identification Number (16 bit unsigned integer): Determines which messages this byte stream contains;
* Message size (16 bit unsigned integer): Number of bytes of the ``Fields'' part of the message;
* Timestamp (64 bit double precision floating point number in IEEE 754 format): The time when the message was sent. The number of seconds is represented in Universal Coordinated Time (UCT) in seconds since Jan 1, 1970;
* Source Address (16 bit unsigned integer): The number that identify, within the IMC network, the system that created this message;
* Source Entity (8 bit unsigned integer): The entity (in general, a Dune task) generating this message at the source address.
* Destination Address (16 bit unsigned integer): The number that identify, within the IMC network, the target system of this message;
* Destination Entity (8 bit unsigned integer): The number that identify, within the IMC network, the target entity of this message, within the target system;

## Fields:

The payload of the message. A finite set of values that carry information according to the definition of the container message. In particular, it can be of any type specified in the IMC schema, including another message or a list thereof;

## Footer (16 bit unsigned integer):

A checksum value, calculated using the CRC-16-IBM with polynomial 0x8005 \((x^16 + x^15 + x^2 + 1)\), that validates and indicates the integrity of the message;

# Serialization and Deserialization

To ensure accurate transportation, some field types may require special treatment on transmission and reception. The operation of preparing a field type for transmission is called serialization, the inverse action is called deserialization. No special process is required for native types, such as integers, floating points and unsigned integers. For "composite" types, we use:

* rawdata
`rawdata` is serialized by prepending a value of type uint16_t, representing the length of the sequence, to the stream of bytes. On deserialization the prepended value is used to retrieve the length of the byte sequence.

* plaintext
`plaintext` is serialized by prepending a value of type uint16_t, representing the length of the sequence, to the stream of ASCII characters. On deserialization the prepended value is used to retrieve the length of the ASCII character sequence.

* message
`message` is serialized by prepending a value of type uint16_t, representing the identification number of the message, to the serialized message payload. The special identification number 65535 must be used when no message is present. On deserialization the prepended value is used to retrieve the correct message identification number.

* message-list
`message-list` is serialized by prepending a value of type uint16_t, representing the number of messages in the list, to the serialized message payload. On deserialization the prepended value is used to retrieve the correct number of messages.