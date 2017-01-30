#!/usr/bin/ksh

#
# gets AIX facts

LSLPP=/usr/bin/lslpp
LSFS=/usr/sbin/lsfs
DF=/usr/bin/df
AWK=/usr/bin/awk
MOUNT=/usr/sbin/mount
GREP=/usr/bin/grep

function get_oslevel {
    oslevel=$(/usr/bin/oslevel -s)
    printf "\"%s\"" $oslevel
    }

function get_build {
    build=$(cat /var/adm/autoinstall/etc/BUILD 2>/dev/null) 
    RC=$?
    if (( $RC != "0" ))
    then
        build=$(cat /etc/BUILD)
    fi
    printf "\"%s\"" $build
    }

function get_lpps {
    printf "["
    first=true
    $LSLPP -Lc |$GREP -v ^# | $AWK -F":" '{print $2" "$3" "$6" "$7}' |sort -u |while read lpp version state type
    do
        if $first
        then
            printf "{ \"name\": \"%s\", \"version\": \"%s\", \"state\": \"%s\", \"type\": \"%s\" }" $lpp $version $state $type
	    first=false
        else      
            printf ",\r\n{ \"name\": \"%s\", \"version\": \"%s\", \"state\": \"%s\", \"type\": \"%s\" }" $lpp $version $state $type
        fi
    done
    printf "] "
    }

function get_filesystems {
    print "["
    first=true
    IFS=":";$LSFS -c|$GREP -v ^# |while read mp dev vfs node type size options automount acct
    do
        dffree=$($DF $mp |tail -1 |$AWK '{print $3}')
        if [ $dffree = "-" ]
        then
            dffree=0
        fi
    
        if $first
	then
	    printf "{ \"mountpoint\": \"%s\", \"device\": \"%s\", \"vfs\": \"%s\", \"node\": \"%s\", \"type\": \"%s\", \"size_total\": \"%s\", \"size_available\": \"%s\", \"options\": \"%s\", \"automount\": \"%s\", \"acct\": \"%s\" }" "$mp" "$dev" "$vfs" "$node" "$type" "$(( size * 512 ))" "$(( dffree * 512 ))" "$options" "$automount" "$acct"
	    first=false
	else
	    printf ", \r\n{ \"mountpoint\": \"%s\", \"device\": \"%s\", \"vfs\": \"%s\", \"node\": \"%s\", \"type\": \"%s\", \"size_total\": \"%s\", \"size_available\": \"%s\", \"options\": \"%s\", \"automount\": \"%s\", \"acct\": \"%s\" }" "$mp" "$dev" "$vfs" "$node" "$type" "$(( size * 512 ))" "$(( dffree * 512 ))" "$options" "$automount" "$acct"
	fi
    done
    printf "] "
    }


function get_mounts {
    print "["
    first=true
    $MOUNT |sed 1,2d | while read line
    do
        #check if fstype is an nfs or cifs, if so there are 8 fields, if not, there are only 7 fields
        nwfs=$(echo $line | egrep 'cifs|nfs')
        if [[ X$nwfs = "X" ]]
        then
            # line is not a network filesystem
            mp=$(echo $line |$AWK '{print $2}')
            $DF $mp |tail -1 |$AWK '{print $2" "$3}' |read dfsize dffree
            if [[ $mp = "/proc" ]]
            then
                dfsize=0
                dffree=0
            fi
            if $first
            then
                printf "{ \"dev\": \"%s\", \"mountpoint\": \"%s\", \"fstype\": \"%s\", \"date\": \"%s %s %s\", \"options\": \"%s\", \"size_total\": \"%s\", \"size_available\": \"%s\" }" $line "$(( dfsize * 512 ))" "$(( dffree * 512 ))"
                first=false
            else
                printf ", \r\n{ \"dev\": \"%s\", \"mountpoint\": \"%s\", \"fstype\": \"%s\", \"date\": \"%s %s %s\", \"options\": \"%s\", \"size_total\": \"%s\", \"size_available\": \"%s\"}" $line "$(( dfsize * 512 ))" "$(( dffree * 512 ))"
            fi
        else
            # line is a network filesystem
            if $first
            then
                printf "{ \"node\": \"%s\", \"dev\": \"%s\", \"mountpoint\": \"%s\", \"fstype\": \"%s\", \"date\": \"%s %s %s\", \"options\": \"%s\" }" $line
                first=false
            else
                printf ", \r\n{ \"node\": \"%s\", \"dev\": \"%s\", \"mountpoint\": \"%s\", \"fstype\": \"%s\", \"date\": \"%s %s %s\", \"options\": \"%s\" }" $line
            fi

        fi

    done
    printf "] "

    }

# main

# print the beginning of the ansible facts dictionary
echo "{\"changed\": "false", \"rc\": "0", \"ansible_facts\": { "
# print the actual facts
echo  \"oslevel\": "$(get_oslevel)" ,
echo  \"build\": "$(get_build)" ,
echo  \"lpps\": "$(get_lpps)" , 
echo  \"filesystems\": "$(get_filesystems)",
echo  \"mounts\": "$(get_mounts)"
# print the closure of the ansible facts dictionary
echo " } }"

