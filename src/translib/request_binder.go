/*
Copyright 2019 Broadcom. All rights reserved.
The term “Broadcom” refers to Broadcom Inc. and/or its subsidiaries.
*/

package translib

import (
	"errors"
	"reflect"
	"strings"

	log "github.com/golang/glog"
	"github.com/openconfig/gnmi/proto/gnmi"
	"github.com/openconfig/ygot/ygot"
	"github.com/openconfig/ygot/ytypes"

	"translib/ocbinds"
)

const (
	GET = 1 + iota
	CREATE
	REPLACE
	UPDATE
	DELETE
)

var ygSchema *ytypes.Schema

func init() {
	log.Flush()
	var err error
	if ygSchema, err = ocbinds.Schema(); err != nil {
		panic("Error in getting the schema: " + err.Error())
	}
}

type requestBinder struct {
	uri             *string
	payload         *[]byte
	opcode          int
	appRootNodeType *reflect.Type
	pathTmp         *gnmi.Path
}

func getRequestBinder(uri *string, payload *[]byte, opcode int, appRootNodeType *reflect.Type) *requestBinder {
	return &requestBinder{uri, payload, opcode, appRootNodeType, nil}
}

func (binder *requestBinder) unMarshallPayload(workObj *interface{}) error {
	targetObj, ok := (*workObj).(ygot.GoStruct)
	if ok == false {
		err := errors.New("Error in casting the target object")
		log.Error(err)
		return err
	}

	if len(*binder.payload) == 0 {
		err := errors.New("Request payload is empty")
		log.Error(err)
		return err
	}

	err := ocbinds.Unmarshal(*binder.payload, targetObj)
	if err != nil {
		log.Error(err)
		return err
	}

	return nil
}

func (binder *requestBinder) unMarshall() (*ygot.GoStruct, *interface{}, error) {
	var deviceObj ocbinds.Device = ocbinds.Device{}

	workObj, err := binder.unMarshallUri(&deviceObj)
	if err != nil {
		log.Error("Error in creating the target object : ", err)
		return nil, nil, err
	}

	rootIntf := reflect.ValueOf(&deviceObj).Interface()
	ygotObj := rootIntf.(ygot.GoStruct)
	var ygotRootObj *ygot.GoStruct = &ygotObj

	switch binder.opcode {
	case CREATE:
		if reflect.ValueOf(*workObj).Kind() == reflect.Map {
			return nil, nil, errors.New("URI doesn't have keys in the CREATE request")
		} else {
			err = binder.unMarshallPayload(workObj)
			if err != nil {
				return nil, nil, err
			}
			err = deviceObj.Validate(&ytypes.LeafrefOptions{IgnoreMissingData: true})
			if err != nil {
				return nil, nil, err
			}
			return ygotRootObj, workObj, nil
		}

	case GET, DELETE:
		err = deviceObj.Validate(&ytypes.LeafrefOptions{IgnoreMissingData: true})
		if err != nil {
			return nil, nil, err
		}
		return ygotRootObj, workObj, nil
	case UPDATE, REPLACE:
		var tmpTargetNode *interface{}
		if binder.pathTmp != nil {
			treeNodeList, err2 := ytypes.GetNode(ygSchema.RootSchema(), &deviceObj, binder.pathTmp)
			if err2 != nil {
				return nil, nil, err2
			}

			if len(treeNodeList) == 0 {
				return nil, nil, errors.New("Invalid URI")
			}

			tmpTargetNode = &(treeNodeList[0].Data)
		} else {
			tmpTargetNode = workObj
		}

		err = binder.unMarshallPayload(tmpTargetNode)
		if err != nil {
			return nil, nil, err
		}

		err = deviceObj.Validate(&ytypes.LeafrefOptions{IgnoreMissingData: true})
		if err != nil {
			log.Error(err)
			return nil, nil, err
		}

		return ygotRootObj, workObj, nil
	}

	return nil, nil, errors.New("Unknown opcode in the request")
}

func (binder *requestBinder) getUriPath() (*gnmi.Path, error) {
	var path *gnmi.Path
	var err error

	path, err = ygot.StringToPath(*binder.uri, ygot.StructuredPath, ygot.StringSlicePath)
	if err != nil {
		log.Error("Error in uri to path conversion: ", err)
		return nil, err
	}

	return path, nil
}

func (binder *requestBinder) unMarshallUri(deviceObj *ocbinds.Device) (*interface{}, error) {
	if len(*binder.uri) == 0 {
		errMsg := errors.New("Error: URI is empty")
		log.Error(errMsg)
		return nil, errMsg
	}

	path, err := binder.getUriPath()
	if err != nil {
		return nil, err
	}

	for _, p := range path.Elem {
		pathSlice := strings.Split(p.Name, ":")
		p.Name = pathSlice[len(pathSlice)-1]
	}

	ygNode, ygSchema, errYg := ytypes.GetOrCreateNode(ygSchema.RootSchema(), deviceObj, path)

	if errYg != nil {
		log.Error("Error in creating the target object: ", errYg)
		return nil, errYg
	}

	switch binder.opcode {
	case UPDATE, REPLACE:
		if ygSchema.IsList() == false || reflect.ValueOf(ygNode).Kind() == reflect.Map {
			var pathList []*gnmi.PathElem = path.Elem

			gpath := &gnmi.Path{}

			for i := 0; i < (len(pathList) - 1); i++ {
				log.Info("pathList[i] ", pathList[i])
				gpath.Elem = append(gpath.Elem, pathList[i])
			}

			log.Info("modified path is: ", gpath)

			binder.pathTmp = gpath
		} else {
			log.Info("ygot type of the node is Map")
		}
	}

	return &ygNode, nil
}
